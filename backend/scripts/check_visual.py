"""Run from backend: python -m scripts.check_visual [screenshot.png].

No network, browser or database writes. With no path, use temporary test images.
"""
import argparse
import json
import math
import tempfile
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings
from app.services.visual_inspection import DinoV2Extractor, VisualError, cosine_similarity

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screenshot', nargs='?', type=Path)
    args = parser.parse_args()
    folder = Path(get_settings().VISUAL_MODEL_DIR)
    extractor = DinoV2Extractor(folder if folder.is_absolute() else BACKEND_DIR / folder)
    try:
        with tempfile.TemporaryDirectory(prefix='dinov2-check-') as temporary:
            if args.screenshot:
                image = args.screenshot
            else:
                from PIL import Image, ImageDraw
                image = Path(temporary) / 'fixture.png'
                fixture = Image.new('RGB', (1366, 768), '#f8f6f0')
                draw = ImageDraw.Draw(fixture)
                draw.rectangle((0, 0, 1365, 90), fill='#112244')
                draw.rectangle((350, 220, 1010, 610), fill='#ffffff', outline='#112244', width=4)
                draw.rectangle((400, 500, 960, 560), fill='#087f74')
                fixture.save(image)
            first, second = extractor.extract(image), extractor.extract(image)
            norm = math.sqrt(sum(value * value for value in first['vector']))
            similarity = cosine_similarity(first['vector'], second['vector'])
            assert len(first['vector']) == 384 and abs(norm - 1) < 1e-6
            assert abs(similarity - 1) < 1e-6
            print(json.dumps({'status': 'passed', 'model': first['modelId'],
                              'revision': first['modelRevision'], 'dimensions': 384,
                              'l2Norm': norm, 'repeatCosine': similarity,
                              'preprocessing': first['preprocessingVersion'],
                              'riskCalculated': False}, indent=2))
    except (VisualError, ImportError) as error:
        print(json.dumps({'status': 'failed', 'code': error.code if isinstance(error, VisualError) else 'dependencies_missing'}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
