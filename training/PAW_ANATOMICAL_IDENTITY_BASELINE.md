# Provisional anatomical hind-paw identity baseline

This separate offline evaluator measures raw RTMPose channel identity on the
existing Dalmatian training sequence, **conditional on the reviewer's provisional
A=right hind, B=left hind mapping**. Anatomical sides are not independently
verified. The COCO `identityState: verified` entries were produced from that same
bulk confirmation; they provide no additional independent evidence.

The existing Benchmark V2, labels, training artifacts and application are
unchanged. Dog02 has no verified anatomical identities and is excluded from
identity scoring. No training, inference, downloads, mapping/threshold tuning,
commits or pushes were performed.

## Provenance and alignment gate

`evaluate_paw_identity_v2.py` pins the source configuration, both annotation
manifests, mapping confirmation, continuity evidence and existing Benchmark V2
report by SHA256. It verifies manifest payload hashes and Dalmatian video,
prediction, metadata, original-video and annotation hashes before scoring.

All 79 exported anatomical points match the original human A/B coordinates and
visibility exactly, including label and image hashes. Their COCO image IDs,
frame indices, dataset IDs, full-frame dimensions and saved prediction context
are checked against source annotations and prediction frames. Every visible
source target must appear exactly once; omitting one fails the gate.

The evaluator decodes the existing prediction-source video in index order with
the installed OpenCV. It verifies all 177 source-frame timestamps and dimensions,
then compares all 46 annotation-frame images pixel for pixel against the saved,
hash-verified reference PNGs. This run passed at **1080×1920**, with no cropping,
scaling or mirroring. The 79 visible targets occupy 42 frames within frames
46–90. The other saved annotation frames contain no visible targets.

The anatomical mapping is taken only from human evidence, never from model
channel names, image side, closest predictions or evaluation-label optimization.
Physical continuity for frames 75–90 also relies on reviewer-provided evidence;
this is not an independent continuity adjudication. Any provenance or alignment
failure stops evaluation before scores or an output report are produced.

## Fixed scoring protocol

- Compare raw `left_back_paw` only with human-reviewed left hind (physical B),
  and raw `right_back_paw` only with human-reviewed right hind (physical A).
  Never permute channels or match to the opposite target for identity recall.
- Use inclusive Euclidean distances of 10px and 20px in original-image pixels,
  inherited from Benchmark V2. All 79 visible targets remain in recall and
  availability denominators; failed detections and missing same-name predictions
  are misses. Nonvisible labels have no localization target.
- Availability means a saved finite same-name coordinate after successful
  detection, regardless of confidence, distance or image bounds. No prediction
  coordinates, scores or availability are changed.
- For spatial swap diagnostics only, require both human paws visible and both
  raw channels available. Flag a swap candidate when the sum of cross-side
  distances is strictly less than the sum of same-side distances. Count equal
  costs separately. Also report how many candidates have both cross-side
  distances within each fixed threshold. These diagnostics never change recall,
  labels or mappings. They do not measure temporal identity switches.
- Recompute the existing identity-agnostic assignment on identical labels and
  require exact agreement with the saved Dalmatian raw Benchmark V2 results,
  including per-frame distances. The saved benchmark is never overwritten.

## Saved-artifact results — 2026-11-10

| Dalmatian raw RTMPose scoring | Recall ≤10px | Recall ≤20px | Visible-target prediction availability |
| --- | ---: | ---: | ---: |
| Provisional anatomical identity | 62/79 = 78.48% | 66/79 = 83.54% | 76/79 = 96.20% |
| Identity-agnostic localization, optimistic upper bound | 65/79 = 82.28% | 71/79 = 89.87% | 76/79 = 96.20% |

Identity recall is lower by 3.80 percentage points at 10px and 6.33 points at
20px. Three visible targets lack same-side predictions. The identity-agnostic
comparison allows assignments to change every frame; it is not evidence of
anatomical identity. Its existing minimum-total-distance rule does not explicitly
maximize threshold hit counts, so “optimistic upper bound” describes its relaxed
identity requirement, not a universal mathematical bound on threshold recall.

| Human anatomical side | Recall ≤10px | Recall ≤20px | Availability |
| --- | ---: | ---: | ---: |
| Left hind (B) | 30/39 = 76.92% | 32/39 = 82.05% | 38/39 = 97.44% |
| Right hind (A) | 32/40 = 80.00% | 34/40 = 85.00% | 38/40 = 95.00% |

**Spatial swap candidates: 4/36 eligible frames (11.11%)**, at source indices
76, 80, 82 and 89; no equal-cost frames. Of these four, one has both cross-side
distances ≤10px and two have both ≤20px. Thirty-seven annotation frames have
both human paws visible, but only 36 also have both predictions available.
The diagnostic denominator therefore differs from recall's all-visible-target
denominator. Missing predictions and single-visible frames cannot establish a
complete two-paw swap. Large localization errors can also favor swapped cost;
the four candidates are not independently verified swap events.

## Reproduce

Run from the repository root with the already installed OpenCV and NumPy;
no downloads or models are needed:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_paw_identity_v2.py -v
PYTHONDONTWRITEBYTECODE=1 python -m training.evaluate_paw_identity_v2 --output tmp/rtmpose-test/paw-tracking-experiment/dalmatian-anatomical-identity-v2-recheck.json
```

The saved report is
`tmp/rtmpose-test/paw-tracking-experiment/dalmatian-anatomical-identity-v2.json`.
Every output uses exclusive creation; select a fresh path for every run.
The report includes human evidence, alignment checks, input/code hashes,
same-side per-frame distances, swap diagnostics and the unchanged identity-agnostic
comparison. The side-specific table above is aggregated from those distances.

Verification passed 15 new identity tests, 14 existing Benchmark V2 tests and
16 existing annotation tests. New tests cover fixed identities, missing frames
and channels, failed detection, inclusive thresholds, out-of-image/low-score
predictions, deterministic ties, input preservation, exclusive output, omitted
targets, provenance tampering, and wrong pixels/timestamps/dimensions/image hashes.

This is development evidence from one existing training dog, not independent
generalization. Source model-exposure declarations are not an independently
audited review history; browser-only drafts were unavailable. Neither these
labels nor the metrics establish validated gait cycles, stride timing or
clinical accuracy.
