# Day 4, Session 2 — Evidence Replay MVP

Implemented locally on `feature/canine-gait-v2`, starting at `94e9f56`.
The MVP targets the existing **web app**. No commits, pushes, deployment,
training, model downloads, dataset edits, or new dependency declarations.
Missing web workspace dependencies were installed from the unchanged pnpm
lockfile using pnpm 10.33.4 and `--frozen-lockfile`.

## Result

A freshly analyzed video appears beside its real motion-activity trace on the
existing saved-result screen. Clicking the graph or using its accessible time
slider pauses/seeks the native video to the nearest measured source interval's
midpoint. Native playback and native seeking update the graph cursor and the
nearest sample readout. The existing player and installed Recharts library
are reused; the results screen was not rebuilt.

The displayed signal is mean absolute frame-to-frame grayscale change, scaled
to 0–1. The graph explicitly describes whole-picture movement. No pose,
contacts, stance/swing, gait accuracy, symmetry, or diagnosis is inferred.

The latest uploaded `File` stays in Router memory, associated with its analysis
ID, across client navigation. Replay owns/revokes its object URL. Videos are
not written into localStorage or retained on the API. Reloading or analyzing
another clip releases access to the previous source; the saved measurements
remain available with an explicit playback-unavailable message. Demo/example
records do not acquire an Evidence Replay panel.

## Source-time correction

Previously the motion trace reconstructed times from rounded nominal FPS, and
the preview's frame controls assumed 30 FPS. Neither established source-time
alignment for variable-rate video.

- Motion decoding now retains each frame's OpenCV decoder presentation time.
- A comparison between frames `i` and `i+1` is positioned halfway between their
  observed source times. A compacted point uses its compared interval's center.
  Thus 60 frames produce 59 samples, without stretching the samples to five seconds.
- The optional `motionTrace.timingSource` field distinguishes `decoder`,
  `nominal-fps`, and `unavailable`. OpenAPI, TypeScript models and API Zod
  validation agree; older results without the field remain readable.
- Replay requires validated decoder timing, a zero source origin, finite
  strictly increasing timestamps, a playable source, and a compatible duration.
  Invalid clocks and unexplained nonzero origins disable replay instead of
  silently manufacturing index/FPS times. Nominal estimates are read-only.
- The player uses seconds, not estimated frame numbers. Graph scale uses the
  browser's media duration; read-only graphs include all observed timestamps.
- The existing `durationSeconds` summary still estimates analyzed length from
  nominal FPS. It is now labeled accordingly; it is not used to rescale the
  replay clock. The variable-rate test exposed why this distinction matters.

S004's original 12 FPS trace still begins at `0.0417 s` and ends at `4.875 s`.
The original clip's frame count, duration summary, motion mean, standard
deviation, coverage and all 59 original trace values/times match Session 1.
The added provenance field establishes which mapping is safe for replay.

## Actual browser and HTTP evidence

The browser regression starts actual Express and Vite servers and existing
headless Chromium. It selects a local video through the real file input,
submits it through `/api/analyze`, runs the actual Python CLI, and opens the
result. There is no mocked successful API response.

The authorized original source is:

`tests/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv`

Temporary browser-playable WebM copies were created under
`/tmp/petlens-day4-session2`; the original was not changed. The derivatives
were separately analyzed, and each was checked against **its own** source
presentation timestamps, rather than assuming conversion preserved the
original container's timestamp precision.

| Actual browser input | Decoded frames | Frame comparisons | Plotted points | Result |
| --- | ---: | ---: | ---: | --- |
| S004 WebM, 12 FPS | 60 | 59 | 59 | PASS |
| S004 WebM, 30000/1001 FPS | 150 | 149 | 120 | PASS |
| S004 WebM, variable frame intervals | 48 | 47 | 47 | PASS |

Every API point's timestamp was independently compared to `ffprobe`
`best_effort_timestamp_time` interval midpoints, allowing 0.000051 seconds for
the API's four-decimal rounding. The observed largest error in these WebM
runs was below `1e-15` seconds. This does not imply sub-frame visual resolution.

Browser checks covered:

- Graph clicks near the beginning, middle and end set native `currentTime`
  to the corresponding real sample time and pause the video.
- `requestVideoFrameCallback` confirmed actual rendered media frames on the
  source presentation timeline. Frames represent the interval around the
  selected midpoint, not invented intermediate pictures.
- Playing the native video advances the graph readout/cursor through media
  `timeupdate` events; the end boundary is handled without overshooting.
- Client navigation back to the result retains the correct source file.
- Reload disables playback and leaves the graph read-only. Missing trace and
  legacy timing metadata have explicit fallbacks; a single real sample renders.
  For these compatibility checks only metadata/points were removed from the
  genuine saved result; no fake measurements were supplied.
- Temporary upload/result directories were empty after analysis.

The original OGV additionally passed a real HTTP upload through the demo's
Vite proxy to the updated Express server: 60 frames, 59 samples,
`timingSource: decoder`. Native browser playback was tested with the WebM
copies; support for the original OGV container was not assumed.

## Checks and reproduction

- **59 API tests passed**, including preserving/rejecting timing provenance,
  legacy result compatibility, uploads, readiness and cleanup.
- **27 web tests passed**, including six new replay tests for bounds,
  sparse/single samples, missing/invalid times, different FPS, and provenance.
- **43 focused Python tests + 9 subtests passed**, including real S004 decoding,
  variable decoder times, invalid clock rejection, missing FPS, and Day 3
  motion/dependency regressions.
- Library declaration builds, API typecheck, web typecheck, API build and web
  production build passed. Vite emits existing tooltip sourcemap and bundle-size
  warnings; they do not prevent the build.
- Browser integration passed on all three real-video derivatives above.

Commands from the repository root (using the session's pnpm installation):

```bash
node_modules/.bin/tsc -b lib/db lib/api-zod lib/api-client-react
COREPACK_HOME=/tmp/petlens-day4-session1/corepack corepack pnpm@10.33.4 --filter @workspace/api-server test
COREPACK_HOME=/tmp/petlens-day4-session1/corepack corepack pnpm@10.33.4 --filter @workspace/silverpaws-beta test
PYTHONPATH=src .venv-canine-v2/bin/python -m pytest -q tests/test_motion_trace.py tests/test_cli.py tests/test_motion_checkpoint.py tests/test_features.py tests/test_pose_fallback.py tests/test_setup_check.py
```

Build the API before the browser regression. Set `SILVERPAWS_PYTHON` if using
a different existing Python environment. The regression starts/stops its own
servers and browser:

```bash
CHROMIUM_PATH=/home/codespace/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome PETLENS_REPLAY_VIDEO=/tmp/petlens-day4-session2/s004-variable.webm PETLENS_REPLAY_EVIDENCE=/tmp/petlens-day4-session2/browser-final node artifacts/silverpaws-beta/tests/evidence-replay.browser.mjs
```

For other environments, choose an installed Chromium executable and an
authorized local browser-playable dog video. No browser installation is performed.
`pnpm --filter @workspace/silverpaws-beta test:replay` runs the same script.

Evidence: `/tmp/petlens-day4-session2/browser12-final`, `browser2997`,
`browser-variable-final`, and `browser-final` contain real analysis JSON,
screenshots and process logs. These are temporary local artifacts, not backups.

## Local demonstration and limits

The updated motion-only API is running on port **8080**, and the existing web
development server on **4173**. The page and original S004 upload through the
web proxy were checked over real HTTP. In a remote workspace, forward port
4173 to reach it from your browser.

Open New analysis, select a pet, upload a browser-playable dog clip, run
analysis, and select a point in Evidence Replay. The existing temporary
`/tmp/petlens-day4-session2/s004-browser.webm` is the 12 FPS demonstration clip.

**Ready for a genuine local web demonstration.** Physical Android/iOS playback,
other browsers/codecs, unexplained stream origins and arbitrary phone files
remain unverified. There is no native Expo implementation, persistent video
library, two-video comparison, pose overlay or contact prediction in this MVP.

## Files changed in this session

- `artifacts/silverpaws-beta/src/components/EvidenceReplay.tsx` (new)
- `artifacts/silverpaws-beta/src/components/VideoFrameScrubber.tsx`
- `artifacts/silverpaws-beta/src/lib/evidence-replay.ts` (new)
- `artifacts/silverpaws-beta/src/App.tsx`
- `artifacts/silverpaws-beta/src/pages/analyze.tsx`
- `artifacts/silverpaws-beta/src/pages/history.tsx`
- `artifacts/silverpaws-beta/package.json` (test scripts only)
- `gait_engine/motion.py`
- `gait_engine/pipeline.py` (trace call only; prior Day 3 fix retained)
- `lib/api-spec/openapi.yaml`
- `lib/api-client-react/src/generated/api.schemas.ts`
- `lib/api-zod/src/generated/api.ts`
- `lib/api-zod/src/generated/types/motionTrace.ts`
- `tests/test_motion_trace.py`
- `artifacts/api-server/tests/saved-result.test.ts`
- `artifacts/silverpaws-beta/tests/evidence-replay.test.ts` (new)
- `artifacts/silverpaws-beta/tests/evidence-replay.browser.mjs` (new)
- This report (new).

Initial working edits/status were preserved under
`/tmp/petlens-day4-session2/originals` and `initial.diff`. Pre-existing tracked
work remains byte-for-byte unchanged except the intentional trace-call addition
in `pipeline.py`; its Day 3 fix remains intact. `architecture.txt`, existing
reports, CLI fixes, RTMPose hash fix and unrelated work were preserved.
