# Day 3 backend verification — November 12, 2026

Branch `feature/canine-gait-v2`, starting at `94e9f56`. Two scoped fixes;
existing unrelated changes preserved. No training, downloads, dependency
installation, UI changes, dataset/checkpoint edits, commits or pushes.

## Baseline and process boundary

- Mobile: `mobile/src/lib/api.ts::requestAnalysis`; web:
  `artifacts/silverpaws-beta/src/lib/analysis-api.ts::requestAnalysis`.
  Both upload multipart field `video` to `POST /api/analyze`.
- `artifacts/api-server/src/routes/analyze.ts` stages a temporary clip;
  `src/lib/analysis-runner.ts` selects Python, spawns `scripts/analyze_clip.py`,
  prefers its atomic JSON file over stdout, maps failures/timeouts, and validates
  results with Zod. The route validates the final response and cleans the upload.
  These HTTP/schema paths were inspected, but could not run locally: Express,
  Zod and esbuild are absent. Building fails on missing esbuild; the existing
  saved-result test fails on missing Zod. They are **not passing checks**.
- The app Python pipeline reads OpenCV frame differences. Optional legacy
  detection/COCO pose falls back to motion. Pose sampling targets 15 FPS over
  at most 20 seconds; it retains container times or marks index/FPS estimates.
  The app response is a summary, not an AP-10K feature export: its motion trace
  uses nominal FPS, diagnostics round FPS to three decimals, and it does not
  export original integer PTS or all raw pose observations.
- Frozen RTMPose is separate: `scripts/analyze_v2_experimental.py` calls
  `src/petlens_gait/inference.py`. It decodes every frame, rejects invalid or
  nonincreasing decoder times and decode-count mismatches, keeps failure rows,
  and saves named AP-10K coordinates and uncalibrated raw scores without smoothing.
  The existing contact preparer additionally requires hash-bound metadata and
  original integer PTS/time-base manifests; an app summary cannot substitute.

## Reproduced failures and fixes

1. The API's default `python3` has OpenCV but lacks SciPy. Both analysis and
   readiness crashed at an eager `gait_engine.gait` import; analysis produced
   no JSON because its import sat outside the CLI error handler.
   `gait_engine/pipeline.py` now loads gait math only where needed, and
   `scripts/analyze_clip.py` catches dependency-loading failures as structured
   JSON with exit code 1 and the request ID. No alternate interpreter or package
   installation was needed for the repaired motion path.
2. Fresh RTMPose output omitted `videoSha256`. The unchanged preparer rejected
   an actual completed neural run with `Prediction/video hash mismatch`.
   `src/petlens_gait/inference.py` now fingerprints input bytes in bounded chunks
   and includes the required field. Validators were not weakened.

Regression tests added in `tests/test_cli.py`, `tests/test_motion_checkpoint.py`
and `tests/test_contact_features.py`. They failed before the corresponding fixes.
They cover missing dependency JSON, motion/readiness without SciPy, and real
S004 decoding with saved-pose replay through the existing preparation validators.
Replay is explicitly distinct from neural inference and creates no labels.

The historical “analysis service could not finish this clip” appears in
`TESTING.md` under the October 18 server-down check: a dead Vite proxy returned
HTTP 500. That record does not demonstrate an inference failure. Today's SciPy
failure was reproduced independently; today's live HTTP path remains unverified.

## Observed integrity and results

The original authorized local S004 OGV completed in the existing virtual
environment before changes: 60 frames, 12 FPS, five seconds, motion-only with
null stride fields. The exact default-interpreter command that crashed before
also completes after the fix, with optional missing Torch reported in diagnostics.
Node -> Python -> saved-result helpers completed that clip in **0.407 seconds**
and recognized a missing video's exit-2 failure. This is not an HTTP/schema test.

| Measurement | Before | After |
|---|---|---|
| Default Python analysis/readiness | SciPy import crash; no JSON | 60-frame motion result; readiness JSON |
| Missing runtime dependency | Traceback only | Failure JSON in stdout and output file |
| Fresh RTMPose preparation | Rejected: missing video hash | Actual neural output accepted: 60 × 69 |
| Full RTMPose runner time | Not recorded | 185.78 seconds; no speedup claim |
| Saved-pose replay preparation | Rejected: missing video hash | 60 × 69; identical feature values/masks |
| Saved-source timing | Valid | Preserved; maximum error below 2e-15 seconds |
| Dalmatian missing pose rows | Frames 78, 85, 106 retained | Same rows retained and masked |

Two actual frozen RTMPose runs completed on the existing S004 lossless working
video, offline with cached weights. The second run's source SHA256 matches
`feedb618a93d0a7f8acddd7a198516405f2afe579d48191553bc75a8346d21cd`.
Its fresh output passes `training.prepare_contact_sequences.build` using new
hash-bound metadata copies and the existing original-frame manifest. Raw pose
rows (including confidence/timestamps), derived features and observation masks
are exactly equal before/after. Both runs produced **zero accepted gait
segments**. This is successful inference/export, not verified gait accuracy.
The first run was not timed; neither model accuracy nor a speed improvement
was measured. Saved-pose replay also passed, independently of neural execution.

The unchanged preparer converted Dog02 (60 × 69, 12 FPS, source time base 1/12)
and Dalmatian (177 × 69, 30000/1001 FPS, time base 1/30000). Channel order is
17 × `[relative_x, relative_y, raw_score, observed]`, then `delta_seconds`.
Float64 source timestamps and int64 PTS survive alongside float32 features.
Dog02 has one masked joint; Dalmatian has 133 masked joints, including 51 absent
points in three missing pose rows. Ten Dalmatian body references exclude those
frames from feature windows. Low scores are reason-coded; scores up to
1.4971554279327393 are retained without clipping. Raw JSON audit data preserves
the original numbers. Neither interpolation nor smoothing fills these inputs.
All anatomical identity and contact-target validity masks in this inspection
are false. No anatomical paw accuracy or gait/contact accuracy was established.

Validation: **95 focused Python tests + 2 subtests passed**. The complete
`pytest -q tests` run had **632 passed + 70 subtests**, with five localhost tests
blocked by sandbox sockets; those **five passed** on the permitted retry.
Thus all **637 repository Python tests** passed across the two runs. Six
dependency-free JavaScript test files passed, including multipart parsing,
capacity gates, explanations, hosting, API address and mobile retry behavior.
Bare `pytest -q` also collects ignored experimental/vendor trees and fails
collection; the repository suite was run explicitly from `tests/`.

## Readiness and next task

**PARTIALLY:** feature conversion and the existing preparer work; full HTTP and
schema integration remain blocked by missing Node dependencies. New clips still
need source PTS manifests and hash-bound metadata. Independent contact/airborne
labels, verified paw/dog identities, appropriate timing/rights evidence and
cohort coverage remain data-readiness blockers. The two-observation exploratory
exercise is not evidence of prediction accuracy. Do not retrain yet.

Next: add a real-video multipart `/api/analyze` integration regression in the
pinned API runtime, covering schema validation, Python errors and upload cleanup.

Local execution evidence is under `tmp/day3-reliability/` and
`/tmp/petlens-day3-*`; these are temporary/ignored artifacts, not Git backups.
