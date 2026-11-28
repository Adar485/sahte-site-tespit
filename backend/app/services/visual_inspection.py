"""Offline DINOv2 screenshot embeddings. No phishing classifier or reference gallery.

The complete viewport is letterboxed, never centre-cropped. References must use
the same weights, preprocessing and capture viewport before cosine comparison.
Heavy dependencies and weights are loaded lazily, once per backend process.
"""
import hashlib
import logging
import math
import threading
import time
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings

logger = logging.getLogger(__name__)
MODEL_ID = "facebook/dinov2-small"
REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"
DIMENSIONS = 384
PREPROCESSING = "rgb-letterbox224-white-imagenet-cls-l2-v1"
# Pin all three files: replacing weights/config must never silently change vectors.
FILE_HASHES = {
    "config.json": "1809f83e3bdb1609a501a610ad4a742f4fd8ae44d72ca4aa0df52d1f2ac8628d",
    "preprocessor_config.json": "14e780d86fa1861f8751f868d7f45425b5feb55c38ca26f152ca5097ab30f828",
    "model.safetensors": "ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1",
}
MESSAGES = {
    "disabled": "Görsel analiz ayarlardan kapatılmış.",
    "screenshot_missing": "Ekran görüntüsü alınamadığı için görsel özellikler çıkarılamadı.",
    "dependencies_missing": "Görsel analiz paketleri eksik. requirements-visual.txt paketlerini yükleyin.",
    "model_unavailable": "Yerel DINOv2 model dosyaları eksik veya doğrulanamadı.",
    "image_invalid": "Ekran görüntüsü okunamadı veya izin verilen boyutu aşıyor.",
    "inference_failed": "Görsel özellikler çıkarılırken bir sorun oluştu.",
}

class VisualError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

@dataclass(frozen=True)
class VisualInspection:
    status: str
    summary: str
    findings: list
    data: dict | None
    error_message: str | None
    duration_ms: int

def normalize_vector(values) -> list[float]:
    vector = [float(value) for value in values]
    if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
        raise ValueError("Expected a finite 384-dimensional vector")
    norm = math.sqrt(math.fsum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 1e-12:
        raise ValueError("Invalid vector norm")
    return [value / norm for value in vector]

def cosine_similarity(left, right) -> float:
    """Raw cosine in [-1, 1], never a probability or risk score.

    Caller must check matching model revision and preprocessing metadata.
    """
    a, b = normalize_vector(left), normalize_vector(right)
    return max(-1.0, min(1.0, math.fsum(x * y for x, y in zip(a, b))))

class DinoV2Extractor:
    def __init__(self, model_dir: Path):
        self.model_dir = model_dir.resolve()
        self._lock = threading.Lock()
        self._model = self._processor = self._torch = None

    def _load(self):
        if self._model is not None:
            return
        try:
            for name, digest in FILE_HASHES.items():
                with (self.model_dir / name).open("rb") as handle:
                    actual = hashlib.sha256()
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        actual.update(block)
                if actual.hexdigest() != digest:
                    raise VisualError("model_unavailable")
        except OSError as error:
            raise VisualError("model_unavailable") from error
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as error:
            raise VisualError("dependencies_missing") from error
        try:
            processor = AutoImageProcessor.from_pretrained(
                str(self.model_dir), local_files_only=True, trust_remote_code=False, use_fast=False,
            )
            model = AutoModel.from_pretrained(
                str(self.model_dir), local_files_only=True, trust_remote_code=False, use_safetensors=True,
            ).to("cpu").eval()
            if model.config.model_type != "dinov2" or model.config.hidden_size != DIMENSIONS:
                raise VisualError("model_unavailable")
        except Exception as error:
            raise VisualError("model_unavailable") from error
        self._torch, self._processor, self._model = torch, processor, model

    def extract(self, screenshot: Path) -> dict:
        # One inference at a time bounds CPU/memory even with concurrent captures.
        with self._lock:
            try:
                from PIL import Image, ImageOps
            except ImportError as error:
                raise VisualError("dependencies_missing") from error
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(screenshot) as source:
                        if source.format != "PNG" or source.width * source.height > 20_000_000:
                            raise VisualError("image_invalid")
                        source.load()
                        width, height = source.size
                        image = ImageOps.pad(source.convert("RGB"), (224, 224),
                                             method=Image.Resampling.BICUBIC, color=(255, 255, 255))
            except VisualError:
                raise
            except Exception as error:
                raise VisualError("image_invalid") from error
            self._load()
            inputs = self._processor(images=image, return_tensors="pt", do_resize=False, do_center_crop=False)
            with self._torch.inference_mode():
                output = self._model(**inputs).last_hidden_state[:, 0, :]
                vector = normalize_vector(output[0].float().cpu().tolist())
            return {
                "schemaVersion": "1.0", "modelId": MODEL_ID, "modelRevision": REVISION,
                "weightsSha256": FILE_HASHES["model.safetensors"],
                "preprocessingVersion": PREPROCESSING, "dimensions": DIMENSIONS,
                "normalized": True, "vector": vector,
                "imageWidth": width, "imageHeight": height,
            }

@lru_cache(maxsize=1)
def _extractor(model_dir: str) -> DinoV2Extractor:
    return DinoV2Extractor(Path(model_dir))

def inspect_screenshot(screenshot: Path | None) -> VisualInspection:
    started = time.perf_counter()
    settings = get_settings()
    code = None
    embedding = None
    if not settings.VISUAL_ENABLED:
        code = "disabled"
    elif screenshot is None:
        code = "screenshot_missing"
    else:
        path = Path(settings.VISUAL_MODEL_DIR)
        path = path if path.is_absolute() else BACKEND_DIR / path
        try:
            embedding = _extractor(str(path.resolve())).extract(screenshot)
        except VisualError as error:
            code = error.code
        except Exception as error:
            logger.warning("Visual inspection failed (%s).", type(error).__name__)
            code = "inference_failed"
    elapsed = int((time.perf_counter() - started) * 1000)
    if code:
        status = "skipped" if code == "disabled" else "unavailable" if code in {
            "screenshot_missing", "dependencies_missing", "model_unavailable"
        } else "failed"
        return VisualInspection(status, "Görsel özellikler çıkarılamadı.", [],
                                {"errorCode": code}, MESSAGES[code], elapsed)
    return VisualInspection(
        "completed", "DINOv2 ile görsel özellikler çıkarıldı; referans karşılaştırması yapılmadı.",
        [{"id": "visual-embedding", "severity": "info", "title": "Görsel vektör hazır",
          "description": "384 boyutlu görsel vektör çıkarıldı. Referans görsel deposu henüz yapılandırılmadığı için benzerlik ve risk puanı hesaplanmadı."}],
        {"embedding": embedding, "closestMatch": None,
         "reference": {"status": "unavailable", "reason": "not_configured", "collectionSize": 0}},
        None, elapsed,
    )
