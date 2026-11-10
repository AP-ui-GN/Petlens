# Paw localization benchmark V2

`evaluate_paw_tracking_v2.py` reads the hash-verified sources in
`paw_annotation_sources.json` and runs the existing association and recovery
algorithms on saved predictions. It does not import the application, train,
download models, decode videos, or run inference. The only data output is a new
JSON report. Existing files cannot be overwritten, including with `--output`.

This measures **identity-agnostic localization**, an optimistic upper bound,
**not proof of correct anatomical or temporal identity**. Human A/B identities
are not mapped to anatomical channels or persistent tracker IDs. The assignment
can switch each frame; no independent identity accuracy is reported. Dalmatian
is the existing training sequence; Dog02 is explicitly exploratory. Neither
sequence establishes independent confirmatory performance. The report records
model-exposed annotation frame counts as an additional limitation.

For each method on identical merged human-labeled frames:

- Use all visible human A/B labels as the denominator. Occluded, uncertain,
  ambiguous and unmarked labels have no localization target.
- Match as many prediction/label pairs as possible, one-to-one, minimizing the
  total Euclidean distance per frame. Exhaustively enumerate the at-most-two-paw
  assignments; break ties by input order. Assignment does not depend on thresholds
  and does not maximize the number of threshold hits.
- Count distances **<= 10px** and **<= 20px** in original image pixels as hits.
  Missing predictions, including frames outside accepted segments, are misses.
- Report prediction availability as assigned labels / visible labels, regardless
  of distance. A distant prediction increases availability but may miss both
  localization thresholds.
- Report whole-video coverage as available points / (2 × all video frames),
  including unannotated frames. This is availability, not localization accuracy.

Raw RTMPose uses saved hind-paw coordinates when detection succeeded, without
confidence or image-bound filtering. Low-score and out-of-image raw coordinates
remain predictions. Tracker/recovery uses existing defaults and only associated,
non-null points from accepted recovery segments. No parameters are tuned against
human labels. Recovery receives a copy of the saved frames and no human labels.

The report includes paired per-video method metrics, per-frame distances and
unmatched labels, the source manifest, and hashes of the evaluator, annotation
utilities, association, transitive observation tracker, and recovery code.

## Verify from the repository root

Only the Python standard library is needed. All source artifacts listed in the
manifest and the existing experimental algorithm files must already be present.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_paw_tracking_v2.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_paw_annotation_data.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m training.evaluate_paw_tracking_v2
```

The default report is
`tmp/rtmpose-test/paw-tracking-experiment/multi-video-localization-v2.json`.
It is a local generated artifact under the repository's existing ignored `tmp/`
directory. If it already exists, preserve it and choose a fresh path:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m training.evaluate_paw_tracking_v2 --output tmp/rtmpose-test/paw-tracking-experiment/multi-video-localization-v2-verification.json
```

Every output path uses exclusive creation. Repeating a command with the same
output path fails without overwriting it. Hash or provenance mismatches fail
before evaluation. These commands never execute the V1 evaluator.

## Verified saved-artifact results

The implementation run passed 14 V2 tests and 16 existing annotation tests.
Recall and availability below use 79 visible labels for Dalmatian and 55 for
Dog02. Coverage uses the entire corresponding video.

| Video | Method | Recall 10px | Recall 20px | Label availability | Whole-video coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Dalmatian (train) | Raw RTMPose | 82.28% | 89.87% | 96.20% | 98.31% |
| Dalmatian (train) | Tracker/recovery | 72.15% | 78.48% | 78.48% | 81.07% |
| Dog02 (exploratory) | Raw RTMPose | 52.73% | 92.73% | 100.00% | 100.00% |
| Dog02 (exploratory) | Tracker/recovery | 34.55% | 60.00% | 61.82% | 46.67% |

These are identity-agnostic localization results only.
