"""DINOv2 contracts and capture -> JSON persistence -> API (no model download)."""
import math
from pathlib import Path

import pytest

from app.db.base import utcnow
from app.models import Analysis, AnalysisModule, PageCapture
from app.services import analyses
from app.services import visual_inspection as visual
from app.services.capture.browser import CaptureOutcome
from app.services.capture.manager import CaptureManager, new_capture
from app.services.capture.storage import ArtifactStore

def vector():
    return [1.0] + [0.0] * 383

def embedding():
    return {"schemaVersion": "1.0", "modelId": visual.MODEL_ID, "modelRevision": visual.REVISION,
            "preprocessingVersion": visual.PREPROCESSING, "dimensions": 384,
            "normalized": True, "vector": vector(), "imageWidth": 1366, "imageHeight": 768}

@pytest.mark.parametrize("values", [[], [0] * 384, [float('nan')] * 384, [float('inf')] * 384, [1] * 383, [1e308] * 384])
def test_invalid_vectors_rejected(values):
    with pytest.raises((ValueError, OverflowError)):
        visual.normalize_vector(values)

def test_cosine_is_similarity_not_risk():
    a = vector()
    b = [0.0, 1.0] + [0.0] * 382
    assert visual.cosine_similarity(a, a) == pytest.approx(1)
    assert visual.cosine_similarity(a, b) == pytest.approx(0)
    assert visual.cosine_similarity(a, [-x for x in a]) == pytest.approx(-1)
    assert sum(x*x for x in visual.normalize_vector([2] * 384)) == pytest.approx(1)

def test_missing_screenshot_and_disabled_do_not_load_model(monkeypatch):
    monkeypatch.setattr(visual, '_extractor', lambda _: pytest.fail('must not load model'))
    monkeypatch.setattr(visual.get_settings(), 'VISUAL_ENABLED', True)
    result = visual.inspect_screenshot(None)
    assert result.status == 'unavailable' and result.data['errorCode'] == 'screenshot_missing'
    monkeypatch.setattr(visual.get_settings(), 'VISUAL_ENABLED', False)
    assert visual.inspect_screenshot(Path('unused.png')).status == 'skipped'

@pytest.mark.parametrize('code', ['dependencies_missing', 'model_unavailable', 'image_invalid', 'inference_failed'])
def test_controlled_failures_hide_paths_and_internals(monkeypatch, code):
    class Broken:
        def extract(self, _):
            raise visual.VisualError(code)
    monkeypatch.setattr(visual.get_settings(), 'VISUAL_ENABLED', True)
    monkeypatch.setattr(visual, '_extractor', lambda _: Broken())
    result = visual.inspect_screenshot(Path('private-directory.png'))
    assert result.status in {'unavailable', 'failed'}
    assert result.data == {'errorCode': code}
    assert 'private-directory' not in str(result)

def test_corrupt_image_and_model_files_are_rejected(tmp_path):
    from PIL import Image
    extractor = visual.DinoV2Extractor(tmp_path)
    bad = tmp_path / 'bad.png'
    bad.write_text('not a PNG')
    with pytest.raises(visual.VisualError, match='image_invalid'):
        extractor.extract(bad)
    image = tmp_path / 'image.png'
    Image.new('RGB', (1366, 768), 'white').save(image)
    with pytest.raises(visual.VisualError, match='model_unavailable'):
        extractor.extract(image)
    (tmp_path / 'config.json').write_text('{}')
    with pytest.raises(visual.VisualError, match='model_unavailable'):
        extractor.extract(image)

def prepare(sessions, store):
    with sessions() as session:
        row = Analysis(submitted_url='https://example.com/', status='running', analysis_mode='url_only', created_at=utcnow())
        row.modules = [AnalysisModule(module=name, status='completed' if name == 'url' else 'skipped', findings=[])
                       for name in ('url', 'visual', 'text', 'html')]
        row.capture = new_capture('https://example.com/')
        row.capture.status = 'running'
        row.capture.started_at = utcnow()
        session.add(row)
        session.commit()
        ids = row.id, row.capture.id
    store.staging(ids[1]).joinpath('screenshot.png').write_bytes(b'fixture')
    return ids

def test_capture_visual_persistence_api_and_history(client, session_factory, monkeypatch, tmp_path):
    store = ArtifactStore(tmp_path, 10_000_000)
    monkeypatch.setattr(analyses, 'artifact_store', lambda: store)
    monkeypatch.setattr(visual.get_settings(), 'VISUAL_ENABLED', True)
    seen = []
    class Extractor:
        def extract(self, path):
            assert path.read_bytes() == b'fixture'
            seen.append(path)
            return embedding()
    monkeypatch.setattr(visual, '_extractor', lambda _: Extractor())
    analysis_id, capture_id = prepare(session_factory, store)
    manager = CaptureManager(session_factory, store, visual_inspector=visual.inspect_screenshot)
    manager._record(capture_id, analysis_id, CaptureOutcome(status='completed', files={'screenshot.png'}, final_url='https://example.com/'), 10)
    assert len(seen) == 1
    with session_factory() as session:
        saved = session.get(Analysis, analysis_id)
        module = next(m for m in saved.modules if m.module == 'visual')
        assert module.status == 'completed' and module.features['embedding']['vector'] == vector()
        assert saved.status == 'partial' and saved.risk_level is saved.risk_score is saved.model_version is None
        assert saved.analysis_mode is None
    result = client.get(f'/api/result/{analysis_id}').json()['result']
    data = result['modules']['visual']['data']
    assert data['embedding']['dimensions'] == 384 and 'vector' not in data['embedding']
    assert data['screenshotUrl'] == f'/api/captures/{capture_id}/screenshot'
    assert data['viewport'] == '1366 × 768'
    assert data['closestMatch'] is None and data['reference']['reason'] == 'not_configured'
    assert result['capture']['screenshotUrl'] == f'/api/captures/{capture_id}/screenshot'
    assert result['risk'] is None
    assert client.get('/api/history').json()['items'][0]['riskLevel'] is None
    # API projection did not mutate the JSON stored in the DB.
    with session_factory() as session:
        assert len(next(m for m in session.get(Analysis, analysis_id).modules if m.module == 'visual').features['embedding']['vector']) == 384

def test_visual_worker_failure_keeps_capture_and_url(session_factory, tmp_path):
    store = ArtifactStore(tmp_path, 10_000_000)
    ids = prepare(session_factory, store)
    def broken(_):
        raise RuntimeError('internal secret')
    manager = CaptureManager(session_factory, store, visual_inspector=broken)
    manager._record(ids[1], ids[0], CaptureOutcome(status='completed', files={'screenshot.png'}), 10)
    with session_factory() as session:
        saved = session.get(Analysis, ids[0])
        assert saved.status == 'partial' and saved.capture.has_screenshot
        modules = {m.module: m for m in saved.modules}
        assert modules['url'].status == 'completed' and modules['visual'].status == 'failed'
        assert 'secret' not in modules['visual'].error_message

def test_no_screenshot_records_unavailable_visual(session_factory, tmp_path):
    store = ArtifactStore(tmp_path, 10_000_000)
    ids = prepare(session_factory, store)
    manager = CaptureManager(session_factory, store, visual_inspector=visual.inspect_screenshot)
    manager._record(ids[1], ids[0], CaptureOutcome(error_code='timeout'), 10)
    with session_factory() as session:
        saved = session.get(Analysis, ids[0])
        assert next(m for m in saved.modules if m.module == 'visual').status == 'unavailable'
        assert saved.risk_level is None

def test_late_worker_cannot_overwrite_interrupted_record(session_factory, tmp_path):
    store = ArtifactStore(tmp_path, 10_000_000)
    ids = prepare(session_factory, store)
    with session_factory() as session:
        capture = session.get(PageCapture, ids[1])
        capture.status = 'failed'
        session.commit()
    manager = CaptureManager(session_factory, store)
    manager._record(ids[1], ids[0], CaptureOutcome(status='completed', files={'screenshot.png'}), 10)
    with session_factory() as session:
        assert session.get(PageCapture, ids[1]).status == 'failed'
    assert not (store.root / ids[0]).exists()
