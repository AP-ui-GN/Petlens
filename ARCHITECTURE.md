# PetLens architecture

## System flow

```text
USER
  ↓
PET PROFILE          artifacts/silverpaws-beta/src/pages/pet.tsx
  ↓
UPLOAD CLIP          pages/analyze.tsx  →  lib/analysis-api.ts
  ↓
VALIDATION           file type / size / duration (UI + API)
  ↓
API                  POST /api/analyze  (multipart video)
  ↓
PYTHON PIPELINE      scripts/analyze_clip.py → gait_engine.pipeline.analyze_clip
  ↓
FRAMES               gait_engine/motion.py
  ↓
POSE (optional)      gait_engine/pose_backend.py
  ↓
FEATURES             gait_engine/features.py, gait_engine/gait.py
  ↓
WELLNESS MODEL       gait_engine/wellness.py
  ↓
AI EXPLANATION       api-server/src/lib/explanation.ts
                     (rule-based text in, optional rewrite out)
  ↓
localStorage         src/lib/storage.ts
  ↓
DASHBOARD / HISTORY  pages/home.tsx, pages/history.tsx
```

The UI never runs the vision pipeline. It sends a file and stores the JSON
that comes back. The web app is the PetLens client built for the dog-pose pipeline.
The phone app in `mobile/` is the Expo client restored from `main` commit
`1093191`, including that commit's screens. It can store a `dog-pose` result.
The web package and folder names retain their historical `silverpaws-beta` identifier; the user-facing application and repository are named PetLens.

## Module map

### Frontend — `artifacts/silverpaws-beta/src`

- `App.tsx` — routes
- `pages/pet.tsx` — profile form
- `pages/analyze.tsx` — upload, review, processing, errors
- `pages/home.tsx` — overview
- `pages/history.tsx` — list + detail (measurements vs interpretation)
- `components/trend-panel.tsx` — saved-walk comparison, split by pipeline
- `lib/storage.ts` — pets and analyses in `localStorage`
- `lib/analysis-api.ts` — upload checks and API error messages
- `lib/report.ts` — browser PDF from a saved record
- `lib/disclaimers.ts` — safety copy used in the footer

### API — `artifacts/api-server/src`

- `routes/analyze.ts` — multipart parse, size cap, temp file, JSON reply
- `lib/analysis-runner.ts` — spawn Python, validate against `@workspace/api-zod`
- `lib/explanation.ts` — optional provider rewrite; invalid text is rejected
- `lib/multipart.ts` — small multipart reader (no extra npm dependency)

### Analysis — `gait_engine/`

- `motion.py` — OpenCV frame motion
- `pose_backend.py` — dog detector and ViTPose++ COCO-17 output; canine landmark interpretation is unvalidated and AP-10K gait metrics remain unavailable
- `sampling.py` — 15 fps samples and the busiest 20-second window
- `features.py` — consistency, coverage, hip stability
- `wellness.py` — factor scores, including mobility and historical change
- `pipeline.py` — chooses `dog-pose` or `opencv-motion`, builds `AnalyzeResult`
- `confidence.py` — pose confidence gate (`modelConfidence`, frames used)
- `clip_quality.py` — duration, resolution, brightness, and motion notes

### Contracts — `lib/`

- `lib/api-spec/openapi.yaml` — `/api/analyze` and `/api/healthz`
- `lib/api-zod` / `lib/api-client-react` — generated from that spec
- `lib/db` — Drizzle stub; unused in the beta

## Human vs AI

**Human-developable:** routing, forms, local storage, upload handling, history
layout, PDF assembly, error messages, disclaimers.

**AI / ML:** pose inference, movement features, gait metrics, factor scoring,
observation text, optional LLM rewrite.

## Measurements vs interpretation

A saved analysis keeps both:

- `measurements` — frames, motion mean/std/coverage, symmetry, hip stability
- `factors` / `overallScore` / `observation` — scores and wording

`None` / “Not measured” means the clip did not support that value. It never
means zero.

## Error handling

| Failure | What the user sees |
| --- | --- |
| Missing / non-video file | 400 with a plain message |
| Unreadable / corrupt video | 400 from the pipeline |
| Upload too large | 413 |
| Python missing or crash | 502 |
| Pipeline timeout | 502 |
| API unreachable | UI: “Could not reach the analysis service…” |
| LLM rewrite invalid | Rule-based observation; `usedLlm: false` |

Temporary upload files are deleted after each request.

## Extensibility

- Sudarshan can change scoring without touching the UI
- Kavin can chart saved records without touching the pipeline
- Abhi can add a model provider without changing `gait_engine`
