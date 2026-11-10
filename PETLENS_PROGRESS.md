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
