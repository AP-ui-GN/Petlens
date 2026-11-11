# ContactVision data adapter checkpoint — November 11, 2026

- Implemented `src/petlens_gait/contact_features.py`, `training/prepare_contact_sequences.py`, and `tests/test_contact_features.py`. Pose-only 69-channel features preserve original timing, raw scores above one, missingness, and separate contact/identity masks. RTMPose and the rule detector are unchanged.
- Saved Dog02 (60/60 frames) and Dalmatian (177/177 frames) conversion artifacts in `reports/contact-feature-readiness-v1/`; reproducible job in `training/contact_sequence_inspection_job.json`. Both remain NOT training-ready, with zero independently adjudicated eligible contact targets. Dog02 stays exploratory-only.
- Relevant validation: 343 tests passed plus 17 subtests, including 60 adapter tests. Existing review HTTP tests passed outside the sandbox after its localhost restriction blocked them.
- `architecture.txt` contains the implementation summary. The prior detailed contract and readiness audit are preserved in `docs/CONTACTVISION_READINESS_AUDIT.md`.
- Next: independently reviewed contact labels, supported paw/dog identity, dog-level split assignment, approval and capture/rights records. No model training, inference, dependency installation, new UI, or annotation finalization was performed.
- Original source videos and saved predictions are tracked. The 152 MB ignored Dalmatian lossless working derivative remains local; current real-data re-conversion/integration tests need it at its recorded path. Exported feature artifacts are preserved in this checkpoint. Unrelated untracked files are not included.

# PetLens checkpoint — November 11, 2026

## Current status — Milestones 4 and 5

This section supersedes the November 10 implementation plan below. The user
explicitly authorized the candidate detector and one real-video evidence pilot.
The annotation validation gate remains unmet; this work does not finalize any
human annotations or establish biological accuracy.

- Milestone 4: `src/petlens_gait/events.py` implements the shared conservative
  CONTACT_SUPPORTED / SWING_SUPPORTED / UNKNOWN candidate state machine.
  Its 108 synthetic tests pass; raw inputs and uncertainty are retained.
- Milestone 5: `src/petlens_gait/ground.py` extracts masked, robust OpenCV ground
  motion, checks an independent background region, and feeds the existing
  detector. No new pose inference, training, identity tracker or UI was added.
- One original Dog02 pilot processed all 60 strictly verified original frames:
  59/59 ground registrations passed, with 197–322 ground inliers per pair.
  Saved identity hypotheses permitted 52 physical-paw motion measurements.
- All 120 hind-paw observations remain UNKNOWN. No justified paw-height reference
  exists in this perspective view: usable clearance observations = 0, candidate
  touchdown/lift-off events = 0, candidate complete sequences = 0.
  Identity uncertainty and raw RTMPose scores outside the detector's [0,1]
  contract cause additional abstentions. No scores were clipped or normalized.
- Validation: 267 tests passed, zero final failures, plus five passing subtests
  (41 extraction + 108 detector + 58 gait + 43 review + 17 legacy/formula tests).
  The unchanged 224-test non-HTTP subset was checked again before checkpointing.
- Original Dog02 human annotations remain non-independent, unfinalized and
  unchanged. They are neither automatic inputs nor validation for these results.

Read `docs/GROUND_EVIDENCE.md` for contracts, safeguards and reproduction.
`architecture.txt` preserves the user's requested Milestone 5 response.
The full traceable JSON and three-frame visual diagnostic are in
`reports/dog02-ground-evidence-v1/`.

## Resume and next step

Branch: `feature/canine-gait-v2`; prior checkpoint: `cd38314`.
The authorized save includes both milestones, tests, calibration, reports and
four small, previously ignored pilot dependencies at their original paths:

- `tmp/rtmpose-test/multi-video-evaluation/inputs/dog02-walking.mp4`
- `tmp/rtmpose-test/multi-video-evaluation/inputs/dog02-conversion.json`
- `tmp/rtmpose-test/multi-video-evaluation/runs/dog02-walking-20261102/manifest.json`
- `tmp/rtmpose-test/paw-tracking-experiment/dog02-identity-association/associated-results.json`

Their bytes remain unchanged and are hash-bound in the pilot diagnostic. Source
video, saved predictions, original frame manifest and other required code were
already tracked. The pilot therefore does not depend on uncommitted model weights
or a rerun of inference or tracking.

Use an existing compatible OpenCV/NumPy/SciPy/pytest environment (the pilot used
`.venv-canine-v2/bin/python`, Python 3.11.18, OpenCV 4.11.0, NumPy 1.26.4).
Virtual environments are local; dependency setup is described in the existing
requirements files and the ground-evidence document. FFmpeg/ffprobe is required.

The exact next scientific step is independently calibrated side-view footage
with a measured support reference at the walking depth and a known depth
corridor. Do not derive that reference from predicted paws or relax thresholds
on Dog02. Independent reviewed strides are still required before event scoring.
No further pilot or annotation experiment is part of this checkpoint.

Older untracked experiment archives, comparison images, the optional Husky ZIP,
empty scratch files, ignored caches, environments and weights remain local and
are not included. Stopping the Codespace preserves saved local files; deleting
it would remove local files that have no separate backup.

---

# PetLens end-of-session checkpoint — November 10, 2026

## Current milestone status

- **Milestone 1 complete:** gait engine audit and Day 1 cycle-detector safeguards
  are present. Tracking gaps/nonfinite positions cannot bridge candidate cycles;
  invalid timestamps/indices fail explicitly. Candidate peaks are not contacts.
  The 58 relevant gait regression tests passed.
- **Milestone 2 planning complete:** ground-relative motion and clearance were
  selected for a future candidate event detector. The decision is preserved in
  [docs/GAIT_EVENT_PLAN.md](docs/GAIT_EVENT_PLAN.md). No detector was implemented.
- **Milestone 3 annotation drafts prepared, not finalized:** the existing viewer
  was reused, strict provenance validation was isolated by explicitly selected
  dataset, and written Dog02 observations were organized into compatible drafts.
- **Zero verified complete gait cycles. Zero complete strides established by
  the written observations.** Identity continuity alone does not establish
  contact/lift-off boundaries, visibility, or support states for all frames.

Branch: `feature/canine-gait-v2`. Pre-checkpoint base: `e0789a1`.
The authorized checkpoint must update only this feature branch, never main.
The local feature branch had no matching remote head at inspection; an explicit
same-name push will publish it. Annotation approval is not part of checkpointing.

## Human evidence and provenance — preserve unchanged

Original saved Dog02 review:
`reports/gait-event-review-v1/reviews/review-d684d28c840a475ba7833f1c045d2504.zip`
SHA256: `e0f0bd2a6ca14ff6cc6cddf89a3495959c3a39ecbc5e0cf99b208589601bda82`.

Draft review:
`reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.review.json`
SHA256: `6aeb2c712374156c722aec42652bbe96a6a79fafbc0c76549bc263c55e29ecdf`.

Uncertainty, source references, original values, and proposed changes:
`reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.proposal.json`
SHA256: `3aae39a680309b84f16dd37137ed6349dc437a805a1a5edf9aecd16d0016b076`.

Readable proposal:
`reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.md`.

Frame/source manifest:
`reports/gait-event-review-v1/frame-manifest.json`.
Its SHA256 remains
`ad0e2b3e9029fc67d397b8622c078ba61022fdb9bf45783902de48ee2eb442e8`.

The original ZIP and original A/B descriptions are intact. Live browser storage
was not accessed or imported. The source ZIP says `no_prior_exposure`; the user
explicitly reported prior model exposure. Only the separate proposal changes
that declaration to `prior_exposure`, retaining reviewer `reviewer-1`. Proposed
frame-0/B23/B52 corrections likewise await approval; they do not overwrite the
saved export. The proposal has `finalized=false` and requires user confirmation.
Uncertain event windows remain separate from definite boundary observations.
No bulk filling of the 120 paw-frame slots was performed.

## Reviewer availability and blockers

Dog02 passed complete provenance validation for all 60 original frames, including
source hash, dimensions, source numbering/native PTS/timestamps, pixel hashes and
PNG hashes. Unselected datasets cannot access review, frame, validation or export
routes. A selected source must pass its full manifest comparison before startup.

Start from the repository root:

```bash
python -m training.gait_event_review --dataset gait-dog02 --port 8767
```

Open `http://localhost:8767/?dataset=gait-dog02`. Forward port 8767 in Codespaces
if necessary. The server was left running during verification; if it or the
Codespace stops, rerun the command. The process itself is not preserved by Git.

Dalmatian remains blocked under default OpenCV 5.0.0. The original video hash
and all frame numbers/timestamps match the saved manifest. One bounded diagnosis
examined only frames 46, 60 and 74: existing OpenCV 4.10 reproduced saved pixel
and PNG hashes exactly; OpenCV 5 showed small intensity differences (mean absolute
channel difference 1.23–1.41/255, maximum 11/255). This supports decoder/conversion
variation, not substantial source-frame misalignment. The precise internal
conversion change was not isolated. The full 177-frame dataset was not verified
in the compatible environment. Do not bypass validation or regenerate the saved
manifest to make it pass. Measurements are saved in
`reports/gait-event-review-v1/dalmatian-decoder-diagnosis.json`.

Missing Dog02 evidence:

- Paw A: last definitely airborne before contact at 19; last definitely
  contacting before lift-off; both definite boundaries of the next contact.
  Frame 56 is a definite human airborne observation; frame 55 is only possible
  lift-off timing.
- Paw B: both initial-contact boundaries before lift-off at 23; last definitely
  contacting before lift-off; both definite boundaries of the later contact.
  The reported 52–59 contact window supplies no exact definite-contact frame.
- Intervening visibility/support states remain unreviewed where not explicitly
  supplied. Sequence-level identity statements do not supply those labels.

## Exact next task

**Continue Milestone 3, not detector implementation:** obtain the user's explicit
approval or corrections to the proposed Dog02 records, especially the exposure
and saved-state conflicts. Keep drafts unfinalized until that approval arrives.
Then collect the missing definite event boundaries and intervening evidence,
seek independent review/adjudication, and reach at least three complete reviewed
strides across two source videos if footage permits. Dalmatian requires full
strict validation in a compatible decoder environment before use. If footage
cannot establish the missing boundaries, retain uncertainty and report the
annotation gate unmet; never fabricate complete cycles.

Only after the annotation gate passes should the next implementation milestone
introduce the planned candidate event detector. No model training, pose inference,
gait-algorithm changes, or annotation approval is authorized by this checkpoint.

## Previously verified tests and checks

```bash
python -m pytest -q tests/test_gait_event_review.py tests/test_gait_cycles.py tests/test_gait_metrics.py tests/test_gait_integration.py
```

**101 passed:** 43 reviewer tests plus 58 gait tests. Local HTTP tests need socket
access; sandbox permission failures were resolved by running outside the sandbox.
Real HTTP verification checked all 60 served Dog02 PNG hashes and blocked
Dalmatian page/session/frame/export routes. Existing headless Chromium opened
original frame 0 and reviewer controls without startup errors. The written draft
also passed the existing validator with zero complete strides and
`independenceDeclared=false`. These checks did not create human evidence.

Checkpoint verification ran the same 101 tests plus blind paw review and
provisional identity regressions in an isolated copy of the staged files:
**123 passed, 39 subtests passed**. The existing Node blind-review UI test
also passed. The staged-copy Dog02 session reverified all 60 source frames and
checked the original ZIP hashes, retained A/B descriptions and unfinalized draft
status. No inference or training ran. The older full anatomical review still
requires its separate local media and was not rerun for this checkpoint.

## Dependencies and durable checkpoint scope

Use Python 3.12 and the pinned offline runtime/test list:

```bash
python -m pip install -r requirements-gait-review.txt
```

This extends the existing `requirements-opencv.txt` pins (OpenCV 4.10.0.84,
NumPy 2.2.6, SciPy 1.15.3) with pytest 9.2.0. System FFmpeg/ffprobe is required
for real-source provenance validation. Node.js is needed for optional JavaScript
UI regressions. No package installation was performed for checkpointing.
CI dependency installation includes pytest so newly preserved regression modules
can be imported. Virtual environments, caches and model weights stay excluded.
The existing compatible decoder environment is
`tmp/rtmpose-test/multi-video-evaluation/.venv/bin/python`; it is not committed.

The explicit checkpoint list includes project gait source, regression tests,
reviewer code/documents, original review and all draft/provenance files. Small
required shared viewer files and offline integration helper scripts/prediction
fixtures under ignored `tmp/` are added by exact path, without changing them.
The original 4.9 MB Dalmatian source video is retained for future strict checks;
Dog02/S003 and S004 source videos were already tracked. Historical small saved
localization/identity reports are preserved without rerunning their evaluators.

Excluded but left intact locally:

- Virtual environments, caches, models and generated frame-image trees.
- The 159 MB lossless Dalmatian derivative and optional historical review media;
  these are not required for the isolated original-source Dog02 reviewer.
- The optional Husky package/extracted media (timing provenance unresolved).
  `tests/PetLens_Husky_ScreenRecording_Test.zip` is not included in this gait
  checkpoint; optional Husky review still needs that local package.
- `artifacts/petlens-pilot-results (1).tar.gz`, Colab package-verification JSON,
  generated model-comparison images, and `reports/rtmpose-paw-v2-diagnosis/`.
  These are prior experimental artifacts outside this focused milestone.
- Empty scratch files `PY~`, `for`, `import`, `logs`, and `p`.

These excluded files are not backed up by this checkpoint and must not be assumed
to survive deletion of the Codespace. Nothing is discarded. Current gait source,
Dog02 review inputs, drafts, required small code dependencies, and provenance are
in scope for the checkpoint. No secrets, credentials, environments, model weights,
or large training bundles are included.

## Archived earlier same-day notes — superseded as current plan

The following earlier checkpoint is retained for historical numerical results.
Its repository-state and next-experiment sections describe an earlier point in
the day; the milestone status and exact next task above take precedence.

# PetLens project checkpoint — 2026-11-10

## Repository state

- Current branch: `feature/canine-gait-v2`.
- Current commit: `e0789a1` (`e0789a1f7034230043d14343a8e9a7c4f2ecd144`).
- This records the current working-tree checkpoint, including local experimental
  artifacts; it does not imply that all referenced work is committed.
- This checkpoint adds documentation only. No training, inference, downloads,
  application changes, or commits are part of this task.

## Today's verified Benchmark V2 results

Source: [training/PAW_TRACKING_V2.md](training/PAW_TRACKING_V2.md).
The saved report is
`tmp/rtmpose-test/paw-tracking-experiment/multi-video-localization-v2.json`.
The recorded verification passed 14 V2 tests and 16 existing annotation tests.
These results are transcribed from the verified run, not recomputed for this checkpoint.

| Video | Method | Recall 10px | Recall 20px | Visible-label prediction availability | Whole-video coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Dalmatian (train) | Raw RTMPose | 82.28% | 89.87% | 96.20% | 98.31% |
| Dalmatian (train) | Tracker/recovery | 72.15% | 78.48% | 78.48% | 81.07% |
| Dog02 (exploratory) | Raw RTMPose | 52.73% | 92.73% | 100.00% | 100.00% |
| Dog02 (exploratory) | Tracker/recovery | 34.55% | 60.00% | 61.82% | 46.67% |

Both methods use the same visible human labels: 79 for Dalmatian and 55 for
Dog02. Each frame uses a one-to-one minimum-total-distance assignment between
predicted hind paws and visible human A/B points. Recall includes all visible
labels in its denominator; missing predictions are misses. Thresholds are
inclusive distances in original-image pixels. Label availability counts assigned
labels regardless of distance; whole-video coverage counts available paw points
over two paw opportunities per video frame, including unannotated frames.

**Raw RTMPose outperforms our existing tracker/recovery pipeline on
identity-agnostic localization and coverage on both evaluated dogs.**
The current pipeline loses useful predictions without demonstrating an offsetting
identity benefit under an independent identity-specific benchmark.

This is **identity-agnostic localization**, an optimistic upper bound, **not proof
of correct anatomical or temporal identity**. Per-frame assignments can switch
freely. No mapping selected using evaluation labels establishes independent
identity accuracy.

## Previous unsuccessful approaches

- **Heuristic temporal trackers V1/V2:** prior attempts have not established a
  reliable improvement over raw RTMPose. The current tracker/recovery combination
  underperforms in Benchmark V2; these paired results do not separately quantify
  every historical tracker variant or establish its identity accuracy.
- **100-iteration RTMPose paw fine-tuning pilot:** did not establish a useful,
  reliable improvement. Existing diagnostic comparisons still show large errors
  and paw swaps. Treat it as an unsuccessful pilot, not evidence that all
  fine-tuning approaches fail or as an independent generalization result.

## Limits of the evidence

- Only two annotated dogs are represented; Dalmatian is a training sequence and
  Dog02 remains exploratory.
- There is no independent generalization evidence. Existing dogs and videos have
  informed development and cannot become untouched test data by renaming a split.
- Existing A/B localization labels do not by themselves establish verified
  anatomical sides or continuity through crossings, occlusions, and gaps.
- There are no verified gait-cycle measurements. Localization or tracking
  coverage does not validate stride timing, gait interpretation, clinical
  accuracy, or arthritis detection. No such clinical claims are supported.

## Next proposed experiment — not yet authorized or implemented

Investigate a lightweight learned temporal identity-association component over
saved raw RTMPose observations. Preserve the raw coordinates and their
availability; predict identity separately and abstain when identity is uncertain.
Abstention must not erase, smooth, interpolate, or move a raw paw observation.
This is a research proposal, not a decision to train or replace the pipeline.

Before training, write and freeze an evaluation protocol covering:

1. **Fair identity-specific benchmark:** compare raw model-channel persistence,
   existing heuristic trackers/recovery, and the learned component on identical
   observations and labeled time windows. Use verified physical A/B continuity.
   If arbitrary IDs need alignment, allow the same single designated human
   anchor for every method per sequence and exclude it from scoring. Never
   optimize a permutation on scored labels or remap per frame. Define restart
   and gap policies in advance. Anatomical accuracy requires separate verified
   anatomical labels.
2. **Label requirements:** human-reviewed temporal identity across continuous
   windows, crossings, and occlusions; visible coordinates; explicit uncertain
   identity, visibility, and gap states; independent review and adjudication of
   disputed events. Define required dogs, videos, windows, and switch events
   before collecting or training; do not fill identity targets from predictions.
3. **Dog/video splits:** keep all frames and clips from a dog in one split,
   including related recording sessions. Use separate development, validation,
   and untouched test dogs/videos. Dalmatian and exploratory Dog02 remain
   development evidence. Add independently annotated dogs before claiming
   generalization; freeze splits and tune thresholds only on validation data.
4. **Regression checks:** require exact preservation of input coordinates,
   timestamps, frame indices, confidence values, and raw prediction availability.
   Re-run Benchmark V2 through the preserved coordinate output: no loss of raw
   10px/20px localization recall or coverage. Test missing observations, swaps,
   ties, gaps, restarts, deterministic output, and identity abstention separately.
5. **Measurable success criteria:** pre-register numeric minimum improvements,
   minimum identity coverage, sample sizes, and uncertainty reporting before
   training. Measure identity switches per eligible transition, correct-identity
   recall over all identity-labeled opportunities, and accuracy versus abstention
   coverage. Missing predictions and abstentions must count against identity
   recall. Require improvement over the strongest baseline at matched identity
   coverage, alongside zero coordinate/availability regression; report paired
   results per dog and video. Do not accept apparent accuracy gains caused only
   by increased abstention. Numeric acceptance thresholds remain to be agreed;
   the training gate is not yet satisfied.

## Checkpoint assumptions

The date uses the workspace's UTC date. Today's numerical results and test counts
come from the existing V2 documentation and prior verification, without a new
benchmark run. Historical approaches are summarized as unsuccessful experiments,
not as universal negative findings. The next experiment and its acceptance
protocol are proposals requiring definition before any training begins.
