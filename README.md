# PetLens

PetLens helps pet owners notice observable changes in how a companion
walks. You save a pet profile, upload a short clip, and the app returns
**measured movement values**, **factor scores you can read**, and a
**plain-language note**. It is a wellness observation tool, not a veterinary
diagnosis.

## Problem

Owners often notice “something looks different” on walks but have no record of
what changed. PetLens turns a short video into a dated note they can compare
over time and, if needed, take to a veterinarian.

## Major features

- Pet profile (name, species, breed, age, weight, notes) stored in this browser
- Walking-clip upload with file, size, and duration checks
- Computer vision pipeline: frame-to-frame picture motion on every clip, and
  a dog box plus the checkpoint's 17 COCO-17 human joint labels when torch and
  weights are installed; canine landmark interpretation is not validated
- Measurements kept separate from interpretation. This pose head does not
  measure stride length, because it has no neck and no base of the tail
- Transparent factor scores (consistency, symmetry, mobility, activity, and
  change from the previous walk) blended into an overall 0–100 indicator
- Rule-based observation text that only quotes measured values
- Optional language-model rewrite when `SILVERPAWS_LLM_URL` and
  `SILVERPAWS_LLM_MODEL` are set; otherwise the rule-based note is shown. After
  three consecutive provider failures, rewrites cool down for 30 seconds while
  the rule-based note continues to work.
- History of saved observations, PDF report, and a veterinarian prompt when
  a change looks concerning

## Architecture

```text
Web UI (React)  →  API (Express)  →  Python pipeline (gait_engine)
                         ↓
                   localStorage  →  dashboard / history
```

| Layer | Location |
| --- | --- |
| Web frontend | `artifacts/silverpaws-beta` |
| API | `artifacts/api-server` |
| Shared contracts | `lib/api-spec`, `lib/api-zod`, `lib/api-client-react` |
| Analysis / CV | `gait_engine/` |
| Database (future) | `lib/db` (schema stub only; beta uses `localStorage`) |

Human-facing code (routing, forms, storage, charts) stays in the frontend.
Pose detection, feature math, scoring, and explanation live behind the API.

## AI components

The wording for each step lives in `lib/ai-use/registry.json` and is copied
into the web app by `node scripts/sync-ai-use.mjs`. The generated page is
`docs/AI_USE.md`. Pose limits are in `docs/MODEL_CARD.md`.

- **RT-DETR** detects dog boxes. **ViTPose++** emits 17 COCO-17 human joint
  labels inside those boxes when torch and weights are installed. The current
  checkpoint has no AP-10K canine keypoint head, and canine landmark
  interpretation has not been validated on a labeled dog-video set. Stride
  length and left/right gait symmetry remain unmeasured. Low-confidence outputs
  are not treated as reliable measurements.
- **OpenCV frame difference** runs on every clip. It is not a learned model.
  When pose is missing, it is the only movement measurement. When pose runs,
  it still supplies movement consistency and activity. Results from different
  pipelines are never mixed in a chart.
- **Scores and the note** come from fixed formulas and templates in
  `gait_engine/wellness.py`. They are not an AI model.
- **Optional language-model rewrite** in
  `artifacts/api-server/src/lib/explanation.ts`, only when
  `SILVERPAWS_LLM_URL` and `SILVERPAWS_LLM_MODEL` are set. Invalid rewrites
  are discarded. The rule-based note is shown instead.
- **Development.** Parts of this app's code and documentation were written
  with AI coding assistants and reviewed by the team. That fact is not a step
  that runs on a clip.

## Limitations

- Does not diagnose injury, pain, or disease
- Does not replace a veterinarian
- Not for emergencies
- One camera angle of one short clip is not a full picture of a pet
- The pose checkpoint is not validated on a labeled set of pet dogs. Its only
  keypoint head is 17 COCO joints. See `docs/MODEL_CARD.md`
- Beta data stays in this browser (`localStorage`), not a shared database

## How to run

Needs **Node.js 24 LTS**, **pnpm 10.33.4**, and **Python 3.10–3.12** with OpenCV.

```bash
pnpm install
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-opencv.txt
```

`requirements-opencv.txt` pins OpenCV and NumPy for Python 3.10–3.12. That
path measures picture motion only and labels the result `opencv-motion`.

For dog pose, install the CPU torch stack (Python 3.10–3.12) and warm the
weight cache so the first request does not download it:

```bash
pip install -r requirements.txt
python scripts/cache_models.py
```

See `docs/MODEL_CARD.md` for what each model is and what it cannot do.

One clip, without the API:

```bash
python scripts/analyze_clip.py path/to/walk.mp4 --pet-name Mabel
python scripts/analyze_clip.py path/to/walk.mp4 --no-pose
python scripts/check_pose_backend.py path/to/walk.mp4 --out outputs/pose-check/
```

`--no-pose` keeps the OpenCV motion result. The pose-review images use the
checkpoint's COCO names. Do not commit the clip or `outputs/`.

Tests:

```bash
python -m unittest discover -s tests -t .
pnpm --filter @workspace/api-server run test
pnpm --filter @workspace/silverpaws-beta run test
```

Run the commands above to validate the current checkout. The pose labels remain
COCO-17 human joints and are not validated canine landmarks. Real canine-video
accuracy has not been established; see `docs/MODEL_CARD.md`.

Start both services (two terminals):

```bash
# terminal 1 — analysis API (port 8080)
pnpm --filter @workspace/api-server run dev

# terminal 2 — app (port 4173), proxies /api to the server
pnpm --filter @workspace/silverpaws-beta run dev
```

Open http://127.0.0.1:4173

To run the API in Docker, see `docs/HOSTING.md`. GitHub Actions builds the
image and smoke-tests readiness plus `POST /api/analyze` with a generated
motion clip. This verifies container packaging and API integration, not canine
pose accuracy or production-host memory use.

### On a phone on the same Wi-Fi

The web dev script already uses `--host 0.0.0.0`. With both services running,
a phone on the same network can open `http://<laptop-ip>:4173`. Use **Record
walk** on the Analyze page to hand the clip to the phone camera through the
file picker. The page does not open the camera itself.

Optional environment variables:

| Variable | Where | Default | Purpose |
| --- | --- | --- | --- |
| `PORT` | API / Vite | `8080` / `4173` | Listen port |
| `BASE_PATH` | Vite | `/` | Public path prefix |
| `API_PROXY_TARGET` | Vite | `http://127.0.0.1:8080` | Dev proxy for `/api` |
| `SILVERPAWS_PYTHON` | API | project `.venv` if present | Python used to run the pipeline |
| `SILVERPAWS_REPO_ROOT` | API | inferred | Repo root so the CLI can be found |
| `MAX_UPLOAD_MB` | API | `60` | Upload size cap |
| `ALLOWED_ORIGINS` | API | localhost Vite origins outside production; empty in production | Comma-separated exact browser origins for the deployed web app |
| `ANALYSIS_TIMEOUT_MS` | API | `600000` | Stop the pipeline after this many milliseconds; valid values are 1 second to 1 hour. Motion saved before pose is returned if pose is still running |
| `SHUTDOWN_TIMEOUT_MS` | API | `15000` | Grace period for active requests when the server receives SIGTERM/SIGINT |
| `ANALYZE_MAX_CONCURRENT` | API | `1` | Pipelines running at once. CPU pose inference defaults to one process to limit memory pressure; extra uploads are refused before the body is read |
| `TRUST_PROXY` | API | unset | Set to `1` only behind a proxy that sets `X-Forwarded-Proto` |
| `SILVERPAWS_LLM_URL` | API | unset | Optional chat-completions endpoint |
| `SILVERPAWS_LLM_KEY` | API | unset | Bearer token for that endpoint; never logged |
| `SILVERPAWS_LLM_MODEL` | API | unset | Model name. Required, with the URL, before a rewrite is attempted |

No API keys are required for the app to analyze a clip.

The repository and user interface use the PetLens name. Existing backend
configuration variables keep the SILVERPAWS_ prefix for compatibility.

For local CORS defaults and production browser-origin configuration, see
`.env.example` and `docs/HOSTING.md`. In production, set `ALLOWED_ORIGINS`
to the exact HTTPS origin(s) of the web app. CORS is not authentication.

## How teammates can contribute

Read `TEAM_TASKS.md`. Each unfinished task points at one file and lists
completion criteria. Do not rewrite working UI or pipeline code to start a
task — extend the function or component that is already marked.

## Documentation

- `ARCHITECTURE.md` — data flow and module boundaries
- `TEAM_TASKS.md` — Sudarshan, Kavin, and Abhi work
- `TESTING.md` — how to verify the app
- `docs/PROJECT_STATUS.md` — what changed, measured impact, per-member handoff
