# Day 3 / Day 4 preservation and staging review

Reviewed November 12, 2026 on `feature/canine-gait-v2`, HEAD
`94e9f56ef66737f171d2e2d80ebad742c577bff9`. This is a proposed commit set;
**no commit or push is authorized or performed**. Staging alone does not back
up these changes to GitHub.

## Scope: 29 explicitly selected text files

Day 3 reliability and provenance fixes:

1. `gait_engine/pipeline.py` — lazy optional SciPy gait import; also includes the
   Day 4 trace call using observed decoder times.
2. `scripts/analyze_clip.py` — structured JSON for dependency-loading failures.
3. `src/petlens_gait/inference.py` — hash the actual video in RTMPose exports.
4. `tests/test_cli.py` — dependency-failure process contract regression.
5. `tests/test_motion_checkpoint.py` — motion/readiness without optional SciPy.
6. `tests/test_contact_features.py` — actual decode with saved-pose replay and
   hash-bound preparation validation; this test is not neural inference.

Day 4 Evidence Replay and source timing:

7. `gait_engine/motion.py`
8. `tests/test_motion_trace.py`
9. `artifacts/api-server/tests/saved-result.test.ts`
10. `artifacts/silverpaws-beta/src/App.tsx`
11. `artifacts/silverpaws-beta/src/pages/analyze.tsx`
12. `artifacts/silverpaws-beta/src/pages/history.tsx`
13. `artifacts/silverpaws-beta/src/components/VideoFrameScrubber.tsx`
14. `artifacts/silverpaws-beta/src/components/EvidenceReplay.tsx` (new)
15. `artifacts/silverpaws-beta/src/lib/evidence-replay.ts` (new)
16. `artifacts/silverpaws-beta/tests/evidence-replay.test.ts` (new)
17. `artifacts/silverpaws-beta/tests/evidence-replay.browser.mjs` (new)
18. `artifacts/silverpaws-beta/package.json` — test scripts only; dependency
    declarations and versions are unchanged.

Backward-compatible API contract and generated output:

19. `lib/api-spec/openapi.yaml`
20. `lib/api-client-react/src/generated/api.schemas.ts`
21. `lib/api-zod/src/generated/api.ts`
22. `lib/api-zod/src/generated/types/motionTrace.ts`
23. `lib/api-zod/src/generated/types/motionTraceTimingSource.ts` (new)
24. `lib/api-zod/src/generated/types/index.ts`

Necessary documentation:

25. `architecture.txt` — latest Evidence Replay summary, replacing previous
    contents as explicitly requested by the user.
26. `docs/DAY3_BACKEND_VERIFICATION_2026-11-12.md` (new)
27. `docs/DAY4_LIVE_BACKEND_2026-11-12.md` (new)
28. `docs/DAY4_EVIDENCE_REPLAY_2026-11-12.md` (new)
29. This review (new).

The generated files were regenerated with **Orval 8.23.0 from the existing
lockfile**. The earlier manual generated edits did not match its exact output.
Regeneration supplies the enum type/constant, type barrel export, and schema
description expected by the existing Actions regeneration check. This is a
packaging correction to the existing timing contract, not a new API behavior.

No datasets, source/derived videos, annotations, checkpoints, weights, image
artifacts, archives, dependencies, build outputs, environment files, secrets,
or force-added ignored files are included. The already tracked original S004
OGV is unchanged and is not part of this staged diff.

## Regression checks rerun during this review

| Check | Result |
| --- | --- |
| Focused Python regression suite | 106 passed + 9 subtests |
| API tests | 59 passed |
| Web tests | 27 passed |
| API and web TypeScript checks | Passed |
| Shared library declaration builds | Passed |
| API and web production builds | Passed |
| API client regeneration | Passed; generated output reviewed |
| AI-use generated registry consistency | Passed |
| Real-video browser integration after regeneration | Passed |
| Full workspace typecheck | Blocked by missing local mockup-sandbox dependency types |

Python command:

```bash
PYTHONPATH=src .venv-canine-v2/bin/python -m pytest -q tests/test_cli.py tests/test_motion_checkpoint.py tests/test_motion_trace.py tests/test_setup_check.py tests/test_features.py tests/test_pose_fallback.py tests/test_contact_features.py tests/test_gait_integration.py
```

API/web tests, typechecks and builds used pnpm 10.33.4. The pinned generator
dependencies were installed using `--frozen-lockfile`; `pnpm-lock.yaml` is
byte-for-byte unchanged. No Python/ML dependencies or weights were installed.

The browser test uploaded the real S004 variable-interval WebM derivative to
actual Express/Python through the actual web UI. It verified 48 decoded frames,
47 source-timed comparisons, graph clicks at start/middle/end, rendered native
media frames, playback-to-graph updates, client navigation, reload, legacy
timing and single-sample fallbacks, missing traces, and upload/result cleanup.
Every plotted time matched the source interval midpoint independently read by
`ffprobe` within the API's rounding precision. No API success was mocked.

The review did not repeat expensive neural inference/training or claim a
new complete Python/Windows/container test run. Session 1's original S004 HTTP
test and Session 2's 12 FPS / 29.97 FPS / variable-interval browser results
remain recorded in the corresponding verification documents.

Local logs and snapshots: `/tmp/petlens-preserve-day3-day4/`. The review's
browser artifacts are in its `browser/` directory. These are temporary local
evidence, not remote backups.

## Existing GitHub Actions failures and dependency limitations

Latest branch run inspected:
[tests #43289696444](https://github.com/AP-ui-GN/Petlens/actions/runs/43289696444),
dispatched November 12, 2026 at `94e9f56`. **API and web jobs succeeded;
Linux and Windows Python jobs failed.** This run predates the proposed staged
changes; no new remote run has been triggered.

Both Python jobs report four errors:

- `tests/test_contact_model.py` calls `pytest.importorskip("torch")`. The
  workflow uses `unittest discover`, which reports that pytest skip exception
  as an import error when optional Torch is absent. Installing large ML
  dependencies is not an appropriate preservation-step workaround.
- Three existing `tests/test_paw_review.py` cases open the ignored local
  Dalmatian derivative. It is not present in a fresh GitHub checkout. A
  pre-existing working-tree fixture repair exists in that file, but it is
  unrelated to the verified Day 3/Day 4 scope and is deliberately **unstaged**.

These remote failures remain open; this checkpoint is not a claim of green CI.
No workflow files were changed. Workflows normally run on PRs to/main pushes
or manual dispatch, rather than every push to this feature branch.

The local full-workspace typecheck stops in `artifacts/mockup-sandbox` with
TS2688 for missing `node` and `vite/client` types because that unrelated
workspace's dependencies are not installed. Focused API/web checks pass.
No ancillary workspace installation or dependency upgrade was performed.

The existing [mobile security review](MOBILE_SECURITY.md) records unresolved
Expo transitive dependency findings from its October 24 snapshot. Mobile
dependencies were not changed and those advisories were not re-audited here.
Vite still emits non-fatal tooltip sourcemap and bundle-size warnings.

## Material review risks

- Replay is a **web motion-activity MVP**, not validated canine pose/contact
  analysis. It retains only the latest video in session memory; reload or a
  later analysis loses playback access to the earlier source.
- Unsupported/nonzero decoder origins or invalid timing disable seeking.
  The summary duration remains nominal-FPS based and is labeled accordingly.
  Physical phones, other browsers/codecs, and arbitrary phone clips remain
  unverified.
- `architecture.txt` intentionally replaces older text. The pre-replacement
  uncommitted contents are preserved under
  `/tmp/petlens-architecture-backups/architecture-20261112T201502327252Z.txt`.
  That temporary backup is excluded from this checkpoint.
- Fresh real-video and saved-pose replay checks need the authorized local
  inputs. The browser regression is opt-in, requires installed Chromium and
  ffprobe, and is not automatically run by the current web Actions job.
- The scope includes the generated enum/barrel correction identified during
  review. It should be committed with the schema and remaining generated files.

## Unrelated work deliberately left unstaged

- `tests/test_paw_review.py` (tracked fixture-portability change).
- `reports/lifelike-mocap-check-2026-11-12/` (five research/evidence files).
- `reports/rtmpose-paw-v2-diagnosis/` (comparison script, metrics, images).
- Four standalone comparison/contact-sheet images in `reports/`.
- `artifacts/petlens-colab-package-verification.json`.
- Pilot/Husky archives and the random initialization checkpoint listed below.
- Empty stray files `PY~`, `for`, `import`, `logs`, and `p`.

All 22 unrelated untracked files and the unrelated tracked test change were
fingerprinted and verified unchanged. Nothing was stashed, deleted or discarded.

## Important local-only artifacts: still not backed up by this staging set

The ten entries in the existing
[local-only artifact inventory](../reports/day2-checkpoint-20261111/local-only-artifacts.json)
were rehashed during this review. All remain present and match their recorded
hashes. Particularly important:

- `outputs/contact-s004-physical-c-v1/last.pt` — 995,736-byte real exploratory
  checkpoint, SHA256 `930c67e805fa2fe65906731e2f476d0a3199a3a7d54beaf7b79212662fbc6789`.
- `tmp/rtmpose-test/multi-video-evaluation/inputs/dalmatian-lossless-cfr.mp4`
  — 159,292,052-byte lossless source derivative.
- `tmp/wikimedia-s004-preparation/s004-lossless-cfr.mp4`, original S004
  prediction JSON, and source-frame manifest bound into existing training jobs.
- Downloaded detector/pose weights in ignored model caches; extracted review
  frames and other ignored source videos/predictions.
- `reports/canine-contact-batch-v1/identity-neutral-exploratory/execution-v1/initial-state-reference.pt`
  — 330,665-byte initialization snapshot, deliberately not staged.
- `artifacts/petlens-pilot-results (1).tar.gz` — 51,671,314 bytes.
- `tests/PetLens_Husky_ScreenRecording_Test.zip` — 12,240,902 bytes.
- Original rejected Nora/Tokyo screening media under `tmp/`.
- Day 3/4 real-run outputs, browser screenshots, HTTP response JSON, temporary
  video derivatives, review snapshots and the architecture backup under
  repository `tmp/` and `/tmp/petlens-*`.

Their presence is not proof of an external backup, and this review does not
create one. Ignored virtual environments, Node dependencies and compiled
outputs also remain local and are intentionally not versioned.
