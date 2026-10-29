# 30-frame gait-data usability summary

- Source predictions: `rtmpose-30-raw-predictions.json`
- Consistency flags: `hind-leg-consistency-report.md`
- Sample: frames 67–96 at 29.97 FPS, about 0.97 seconds from first to last frame.
- No predictions were changed, smoothed, or relabeled.

## Usability by frame

Seven of 30 frames (23.3%) have a hind-paw warning:

- Frame 67: low-confidence left back paw.
- Frame 77: low-confidence left back paw.
- Frames 87–90: low-confidence back-paw predictions; both back paws are low at frame 87.
- Frame 91: part of the sudden two-paw jump and possible left/right identity ambiguity from frame 90 to 91.

The other 23 frames (76.7%) do not trigger the current checker rules. That does not prove their poses are correct; the score and jump thresholds are experiment heuristics.

The uninterrupted unflagged runs are:

| Frames | Number of frames | Elapsed time from first to last |
|---|---:|---:|
| 68–76 | 9 | 0.267 s |
| 78–86 | 9 | 0.267 s |
| 92–96 | 5 | 0.133 s |

The longest unflagged run is therefore only about 0.27 seconds.

## What this supports

The clean runs are long enough for exploratory visual review of short-term paw movement and to identify candidate periods when a paw moves. They are not long enough to reliably measure a full walking cycle: the warnings break up the trace, and the longest uninterrupted run is less than a third of a second.

Do not treat this sample as a reliable measure of stride duration or cadence, stance-versus-swing time, stride length, left/right symmetry, or cycle-to-cycle regularity. Those measurements need longer, continuous footage containing multiple complete cycles, with the paws visible and their left/right identities stable.

## Bottom line

Although 23 frames pass the current simple checks, the usable data are split into short fragments. This sample is suitable for exploratory inspection, but not for a dependable gait-cycle measurement or final gait score.
