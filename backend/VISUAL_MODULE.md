# DINOv2 visual module


Install with the same Python executable used by the backend (Python 3.10+):

```powershell
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-visual.txt
python -m scripts.check_visual
```

Model: `facebook/dinov2-small`, revision `ed25f3a31f01632728cabb09d1542f84ab7b0056`.
Files live in `../models/dinov2-small/`: config.json, preprocessor_config.json,
model.safetensors. They are ignored by Git; each teammate needs the same files.
Source: https://huggingface.co/facebook/dinov2-small/tree/ed25f3a31f01632728cabb09d1542f84ab7b0056
The service verifies SHA256 of all three files once when loading. It never downloads
weights, runs remote model code, or installs packages. `VISUAL_ENABLED=false` disables
extraction; `VISUAL_MODEL_DIR` can select another local folder containing these exact files.
Heavy imports/weights load at first capture; missing packages/model affect only this module.

Flow: URL inspection -> Playwright capture -> DINOv2 extraction on the worker thread
-> capture + visual result saved together -> result/history endpoints -> visual tab.
There is no DB connection held during inference. A model instance is cached per backend
process; inference uses CPU, eval/inference_mode, and one-at-a-time locking.

Preprocessing v1: PNG -> RGB -> aspect-preserving bicubic resize with white padding
to 224x224 (entire viewport, no centre crop) -> the model's ImageNet normalization
-> final CLS token -> finite, 384-dimensional, L2-normalized vector. This deliberate
letterbox policy differs from the checkpoint's default centre crop. Future reference
images MUST use identical capture viewport (1366x768), weights and preprocessing.
Low resolution can lose small text/details; embeddings alone do not prove impersonation.

Storage: existing `analysis_modules` row with `module=visual`, JSON `features.embedding`.
The full vector, model ID/revision/hash, preprocessing version, original dimensions and
normalization flag are persisted; no new table or migration is needed. The API strips
the vector and returns metadata. The UI uses the existing screenshot endpoint; raw files
and filesystem paths are not exposed. Existing records are not recomputed automatically.

Until a real reference gallery exists, `reference.status=unavailable`,
`reason=not_configured`, `closestMatch=null`. Extraction may be `completed` while
comparison remains unavailable. The parent stays `partial`; all risk fields and the
classifier model version stay NULL. For successful visual extraction, legacy
`analysis_mode` is NULL (the UI labels the actual scope as URL + visual features).
No cosine score, threshold, trained classifier or probability is invented. The helper
`cosine_similarity` returns raw [-1,1] only; callers must verify matching model and
preprocessing metadata before comparing future references.

Verification:

```powershell
python -m pytest -q tests/test_visual.py --basetemp=.pytest_work/visual
python -m scripts.check_visual
# Optional: check an existing captured PNG without visiting the site again
python -m scripts.check_visual var/captures/<analysis-id>/<capture-id>/screenshot.png
```

Unit/integration tests use controlled embeddings and SQLite to verify persistence,
API/history contracts, missing/corrupt files, worker failures, cancellation and no risk
fabrication. `check_visual` uses the actual local weights and checks 384 dimensions,
finite unit-length output and identical-image repeat similarity. These are correctness
checks, not phishing detection accuracy measurements. MySQL/live browser verification
must be run separately against a local configured instance.


Verified on 2026-11-28 in the agent's Python 3.12 test environment:
- 17 visual tests + 6 existing API tests passed (23 total).
- Four existing frontend tests and the production build passed.
- Real local DINOv2 inference passed: dimensions=384, L2 norm=1, repeat cosine=1.
- Real MySQL persistence, result/history GET and screenshot GET passed. Test records
  and artifacts were removed; original table counts [1, 0, 0] were restored.
- The broader URL run had 200 passes and two existing failures: invalid bracketed
  host inputs return `malformed` rather than `invalid_host` under Python 3.12.
  The committed parser is unchanged; urllib rejects these before host validation.
- A browser capture test using installed Chromium 1248 with the test environment's
  newer Playwright timed out. The broader browser run was stopped. Full capture
  regressions and browser UI verification are not claimed to pass in this environment.
- User Python 3.10 could not be executed from this session. Dependencies installed
  for these checks are in the agent workspace, not the user's Python installation.
  Run the installation commands above with the backend's Python before using the module.
