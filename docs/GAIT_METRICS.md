# Gait metrics

These are measurements from an AP-10K keypoint array. They are not a diagnosis.
The current pose checkpoint does not emit that array. Its 17 channels are
COCO joints, so a real clip leaves these stride numbers unmeasured. The
formulas below still apply when an AP-10K array is supplied.
A missing value is null. The screen says "Not measured". It is never shown as 0
or as 1.0.

Image y grows downward. Distances that are divided by body length are in body
lengths. Times are seconds.

## Preparation

A keypoint with score below `KEYPOINT_MIN_SCORE` (0.3) is missing. Gaps of at
most 3 sampled frames are filled by linear interpolation. Longer gaps stay
missing. Savitzky–Golay smoothing (window 5, polynomial order 2) runs on
contiguous stretches of at least 5 samples.

Body length `L` is the median, over frames, of the pixel distance from the
neck to the root of the tail. The forward axis is that same vector, normalized,
then median-filtered. Front paws are measured from the mean of the two
shoulders. Rear paws are measured from the mean of the two hips.

`pawX(t) = dot(paw - reference, forward) / L`

## When a number stays null

Side-on gate: the median of `|neck_x - tail_x| / dog_box_height` must be at
least `MIN_SIDE_ON_RATIO` (0.6). If it fails, `view.sideOn` is false, stride
metrics are null, and the reason is "Film from the side with the whole dog in
frame."

A pair (front or rear) is null unless both paws have at least `MIN_STRIDES`
(3) kept stride intervals and both paws are present on at least 60% of frames.
If the two paws move in phase, the pair is null and the reason is "Left and
right legs could not be told apart." The report does not say which side is
weaker.

`symmetryReliable` is true only when the view is side-on, the dog was found
in at least 60% of sampled frames, and at least one pair was measured.

Head-bob and pelvis asymmetry need at least 6 downward dips. Otherwise they
are null. Left-versus-right hip height is not computed. That comparison needs
a head-on view, which this side-on pipeline does not use.

## Stride

Peaks of `pawX` use `scipy.signal.find_peaks`. These cutoffs are placeholders
to calibrate on labeled clips:

| Name | Value | Role |
| --- | --- | --- |
| `PEAK_PROMINENCE_BODY_LENGTHS` | 0.15 | Minimum peak prominence |
| `MIN_PEAK_SPACING_SECONDS` | 0.4 | Minimum time between peaks |
| `STRIDE_INTERVAL_MIN_SECONDS` | 0.4 | Shortest kept same-paw interval |
| `STRIDE_INTERVAL_MAX_SECONDS` | 2.5 | Longest kept same-paw interval |
| `ANTI_PHASE_LOW` / `ANTI_PHASE_HIGH` | 0.35 / 0.65 | Accepted phase difference, as a fraction of one stride |

Per paw, `strideCount` is the number of kept intervals. `excursion` is the
median of (peak − trough between that peak and the next), in body lengths.

Pair symmetry is `S = 1 - |A_left - A_right| / (A_left + A_right)`.
`asymmetryPercent = (1 - S) * 100`. `limbSymmetry.front` and `.rear` are `S`.
`strideSymmetry` is the lower of the measured pairs. `strideLengthBodyLengths`
is the mean excursion of that pair.

The optional signed index uses the same paired excursions:
`SI = 200 * (A_left - A_right) / (A_left + A_right)` and `ASI = |SI|`.
Positive SI means the left excursion is larger; negative means the right is
larger. For non-negative excursions, `SI` is bounded by `[-200, 200]`, and
`S = 1 - ASI / 200`. `limbSymmetryIndex.front` and `.rear` contain these
signed and absolute values when the pair is measured. They describe normalized
paw excursion, not calibrated stride length or a clinical severity scale.

`cadenceStridesPerMinute` is `60 / median(kept same-paw intervals)` from the
pairs that were measured. `strideTimeCv` is the standard deviation of those
intervals divided by their mean.

Phase uses the lag of the cross-correlation peak inside one stride period,
divided by that period.

## Vertical

Nose (head), neck (withers), and root of the tail (pelvis) use image y
divided by `L`, minus a 1-second moving average. `headVerticalOscillation`
and `pelvisVerticalOscillation` are the standard deviation of that residual,
in body lengths. Neck is used as a landmark and is not given its own
oscillation score.

`headBobAsymmetry` and `pelvisAsymmetry` compare the two dips in each stride:
`mean(|A_odd - A_even|) / mean(A)`, using peak prominence. They need at least
6 dips.

## Scores that use these measurements

The symmetry factor is `100 * strideSymmetry` when symmetry is reliable.
Mobility is the mean of the available parts among:

- stride regularity: `100 * clamp(1 - strideTimeCv / 0.25, 0, 1)`
- vertical symmetry: `100 * clamp(1 - mean(available asymmetry indices) / 0.5, 0, 1)`

Mobility is null when neither part was measured. Movement consistency,
activity, and change from the previous walk are unchanged. `CONCERNING_DROP`
stays 10 and `CONCERNING_ASYMMETRY` stays 20. Those thresholds were chosen
for the previous symmetry definition and still need a review against this one
after a labeled clip set exists.
