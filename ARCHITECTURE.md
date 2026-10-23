# PetLens architecture

## Components and data flow

```text
Web app (React) ─┐
                 ├─ video upload ─> Express API ─> Python analysis pipeline
Mobile app (Expo)┘                                  │
                                                   ├─ OpenCV frame motion
                                                   ├─ optional RT-DETR dog detection
                                                   └─ optional ViTPose++ COCO-17 output
                                                            │
                                 OpenAPI/Zod-validated JSON <┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                  Web localStorage          Mobile AsyncStorage
                  dashboard/history         local pet and walk history
```

The API does not persist user profiles or analyses. Each client stores its
own records locally; data is not shared between devices or accounts.

## Responsibilities

| Component | Location | Responsibility |
| --- | --- | --- |
| Web app | `artifacts/silverpaws-beta/src` | Pet profiles, video upload, analysis display, browser-local history, trends, and reports |
| Mobile app | `mobile/src` | Expo screens, video upload with progress, phone-local history, settings, and reports |
| Analysis API | `artifacts/api-server/src` | Validate multipart uploads, apply request limits, call the Python process, validate responses, optionally rewrite explanation text, and clean up uploaded files |
| Python pipeline | `gait_engine/`, `scripts/analyze_clip.py` | Decode/sample video, measure frame motion, optionally detect dogs or produce pose output, and assemble a result |
| API contract | `lib/api-spec/openapi.yaml` | Source schema for the API |
| Generated clients | `lib/api-zod`, `lib/api-client-react` | Runtime response validation and web client generated from the API specification |

## Analysis boundaries

Every successful analysis measures generic frame-to-frame picture motion with
OpenCV. If dependencies and weights are available, RT-DETR can report dog
detections on sampled frames and tracking metadata. The optional
`usyd-community/vitpose-plus-base` checkpoint has a human COCO-17 output head;
it is not canine pose and is disabled by default. Set
`PETLENS_ENABLE_EXPERIMENTAL_COCO_POSE=true` only for local inspection. The app
does not use those joints to report canine stride length or left/right gait
symmetry. Missing measurements remain `null` rather than being inferred or
set to zero.

Factor scores and rule-based observations are computed in
`gait_engine/wellness.py`. An optional server-side language-model rewrite is
implemented in `artifacts/api-server/src/lib/explanation.ts`; the result is
validated and rejected if it invents measurements or makes unsupported
medical claims.

## Saved data

The browser stores profiles and analysis results in `localStorage`. The phone
stores them in `AsyncStorage`. Uploaded video is written to a temporary
directory for processing and removed after the request. No database or
cross-device account sync is currently implemented; `lib/db` is not used by
the beta application.

## Run and test

Install steps and the exact current model limitations are in
[`README.md`](README.md) and [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

Start the API and web app in separate terminals:

```bash
pnpm --filter @workspace/api-server run dev
pnpm --filter @workspace/silverpaws-beta run dev
```

Run Python, API, web, and (when its dependencies are installed) mobile checks
using the commands documented in `README.md` and `mobile/package.json`.
