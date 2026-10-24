# PetLens

PetLens turns a short pet-walking video into a saved movement observation.
It helps owners notice and discuss visible changes with a veterinarian. It
does **not** diagnose pain, injury, or disease.

## What PetLens measures today

| Capability | What it means |
| --- | --- |
| Video motion | OpenCV compares frames to summarize picture movement. This is not a measurement of a particular leg or of gait health. |
| Dog detection (optional) | RT-DETR can report dog detections on sampled frames, whether a person was seen, and whether multiple dogs made tracking ambiguous. |
| Pose output (optional, experimental) | The available ViTPose++ checkpoint outputs 17 **human COCO** joints. These are not validated canine landmarks and are not used to calculate dog stride symmetry. |
| Stride and gait health | Not currently measured. Stride symmetry, stride length, and clinical conclusions are not available. |

When pose processing is unavailable or fails, the app can still return a
motion-only result. If the detector is also installed and its weights are
cached, dog-detection metadata is retained without inventing pose or gait
values. Missing measurements remain unavailable in the result.

The web app saves pet profiles and observations in that browser's
`localStorage`; this beta does not use a shared database. See
[`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) for model details and validation
status.

## Run locally

Install Node.js 24, pnpm 10.33.4, and Python 3.10–3.12. From the repository
root:

```bash
pnpm install
python -m venv .venv
```

Activate the virtual environment, then install the lightweight motion
pipeline:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-opencv.txt
```

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements-opencv.txt
```

Start the API and web app in **separate terminals**:

```bash
pnpm --filter @workspace/api-server run dev
```

```bash
pnpm --filter @workspace/silverpaws-beta run dev
```

Open <http://127.0.0.1:4173>. The web development server forwards `/api`
requests to the API on port 8080. The default Python setup supports OpenCV
motion analysis; it does not download AI weights.

### Optional detector and pose dependencies

To enable RT-DETR dog detection, install the pinned CPU dependencies and cache
the models:

```bash
pip install -r requirements.txt
python scripts/cache_models.py
```

This downloads model weights. By default, the app uses RT-DETR for dog
detection only; it does not return pose landmarks. To explicitly opt into
experimental ViTPose++ COCO-17 output for local inspection, set
`PETLENS_ENABLE_EXPERIMENTAL_COCO_POSE=true` before starting the API. These are
human-joint labels, not validated canine anatomy, and they do not enable
stride measurements. Cached weights live under `models/hf` by default and
are not part of the source code. The API readiness endpoint is
`http://127.0.0.1:8080/api/readyz`.

## Analyze a video from the command line

```bash
python scripts/analyze_clip.py path/to/walk.mp4 --pet-name Mabel
```

To skip pose and use motion analysis only:

```bash
python scripts/analyze_clip.py path/to/walk.mp4 --no-pose
```

For local inspection of pose output, use `scripts/check_pose_backend.py`.
Review images and videos are generated artifacts; do not commit private clips
or their outputs.

## Checks

Run the Python suite and the API and web checks from the repository root:

```bash
python -m unittest discover -s tests -t .
pnpm --filter @workspace/api-server typecheck
pnpm --filter @workspace/api-server test
pnpm --filter @workspace/silverpaws-beta typecheck
pnpm --filter @workspace/silverpaws-beta test
pnpm --filter @workspace/silverpaws-beta build
```

The Expo mobile client is a standalone npm project:

```bash
cd mobile
npm ci
npm run typecheck
npm run doctor
npm run export:check
```

The current mobile dependency security review, including unresolved
transitive advisories, is documented in
[`docs/MOBILE_SECURITY.md`](docs/MOBILE_SECURITY.md).
For an installable Android APK, production API setup, and EAS build
instructions, see [`docs/MOBILE_RELEASE.md`](docs/MOBILE_RELEASE.md).

## Project structure

| Area | Location |
| --- | --- |
| Web app | `artifacts/silverpaws-beta` |
| API | `artifacts/api-server` |
| API contract and generated clients | `lib/api-spec`, `lib/api-zod`, `lib/api-client-react` |
| Video analysis and measurements | `gait_engine/` |
| Model status and audit | `docs/MODEL_CARD.md`, `docs/model_audit.md` |

For deployment and hosting configuration, see [`docs/HOSTING.md`](docs/HOSTING.md).
For a no-cost, motion-only Render preview, see the "No-cost motion-only Render preview" section.
For the architecture, see [`ARCHITECTURE.md`](ARCHITECTURE.md).
