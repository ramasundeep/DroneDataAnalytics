# services/assessment — metrics and rubric scoring

Turns recorded sessions into scores. Full spec: `docs/06_ASSESSMENT_ENGINE.md`.

| Piece | Status |
|---|---|
| `scoring.py` — band scoring, weights, pass threshold, critical metrics | ✅ deterministic, tested |
| `POST /v1/score`, `POST /v1/rubrics/validate`, `GET /v1/rubrics` | ✅ |
| `metrics.py` — metric definitions (docstrings are normative) | ⚠️ `landing_*` implemented; others raise `NotImplementedError` until Phase 3 |
| Session assessment from recordings, audio VAD, PDF/JSON reports | ⏳ Phase 3 |

Rubrics live in `rubrics/*.yaml` (schema `schemas/json/rubric.schema.json`).
Thresholds in the shipped rubrics are placeholders pending instructor calibration.
