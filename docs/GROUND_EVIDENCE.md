# Candidate ground evidence: fixed first approach

This offline path reads original video pixels and existing saved predictions.
It neither runs a model nor reads human gait/identity annotations. Outputs are
engineering candidates, with no assertion of biological contact or accuracy.
The existing event detector, its thresholds, historical predictions and human
annotations are unchanged.

## Registration

`src/petlens_gait/ground.py` uses one shared `GroundRules` configuration:

1. Select independently inspected floor and background polygons. Exclude the
   padded saved dog detection in both frames and any independently inspected
   handler/person regions. Missing detection or unsupported foreground coverage
   causes abstention.
2. Detect up to 400 Shi–Tomasi corners per region; track with pyramidal
   Lucas–Kanade in both directions. Reject bad status, nonfinite coordinates,
   forward/backward error above 0.75 pixels, high patch error and masked endpoints.
3. Fit a previous-to-current 2D similarity using RANSAC. Require at least 12
   inliers, 75% inliers, distributed support (convex-hull area at least 10% of
   available region), median residual at most 0.75 pixels and 95th-percentile
   residual at most 1.5 pixels. Keep all accepted feature matches, inlier flags,
   residuals and candidate transforms in the diagnostic JSON.
4. Fit the separate background independently. Its predicted motion at the floor
   polygon vertices must agree within 1.5 pixels. Otherwise reject the ground
   interpretation, including a coherently moving floor with a stationary wall.
   A scene whose surface is moving or unsupported abstains before registration.
5. Warp the previous paw into the current frame using the accepted floor
   transform. Subtract it from the current observed paw. Normalize this residual
   by native elapsed seconds and the current torso length from the existing
   `anatomical_reference` utility. Never substitute body-relative or raw pixel
   speed when ground registration is absent.

OpenCV documents [pyramidal sparse optical flow](https://docs.opencv.org/4.x/dc/d6b/group__video__track.html)
and [robust partial affine estimation](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html).
The gates above are engineering choices fixed on synthetic scenes, not validated
biological thresholds. Ground/background agreement is only a consistency check;
coherently moving visible structures may be indistinguishable from camera motion.
The explicit static-surface assumption remains a limitation. Parallax,
perspective changes and a broken cumulative calibration cause abstention; there
is no fallback that assumes a stationary camera and no automatic reset.

## Proximity and identity

A visible floor polygon permits only an image overlap diagnostic. Its arbitrary
boundary, or a wall/floor seam at another depth, cannot provide paw clearance.
Projected clearance is available only with an explicitly supplied support line,
independent of predicted paws, a supported depth corridor and sufficiently small
calibration uncertainty. Registration residuals accumulate into line uncertainty.
These are 2D measurements, never 3D height, force, weight bearing or verified contact.

Dog02's reference selects scene texture from the original video. The floor is a
region in perspective, and the back seam is behind the walking plane. Accordingly
`clearanceReference` is null. No paw-ground line is manufactured from predictions.
The event detector must abstain without clearance, even when motion is measured.

The pilot reads the pre-existing `dog02-identity-association/associated-results.json`.
These are uncertain, arbitrary hind-paw IDs 0/1, independent of human A/B names.
The embedded original predictions must match the hashed saved predictions;
associated points must be exact unchanged source points. Only adjacent accepted
assignments can support a physical-paw displacement. Unresolved assignments and
gaps break continuity; no tracker is run and no identity is reconnected here.
Separate model-channel displacement diagnostics never supply identity continuity.

RTMPose `rawScore` is uncalibrated and can exceed one. Raw values are preserved.
The existing detector requires confidence in [0,1]; out-of-range scores therefore
remain unavailable at that gate, with an explicit reason. No clipping or arbitrary
score normalization is performed. Uncalibrated in-range scores remain quality
gates, not contact probabilities.

## Original-source pilot and reproduction

From the repository root, using the existing OpenCV environment:

```bash
.venv-canine-v2/bin/python scripts/run_ground_evidence_pilot.py \
  --output reports/dog02-ground-evidence-v1
```

Use a new output directory for any independent reproduction; the script refuses
to overwrite a previous result. It calls the existing selected-source
`training.gait_event_review.session(group='gait-dog02')` verification and frame
decoder, reading only the source/frame manifest, never reviews. This verifies the
original source hash, native integer PTS, dimensions, frame count, pixel hashes
and lossless PNG hashes for all 60 frames. Saved source configurations, inference
artifact hashes and conversion metadata bind the lossy inference derivative to
the original: every frame/time and dimension must align. Original native PTS are
used for measurements; original prediction timestamps remain alongside them.
Lossy derivative and original pixels are not asserted identical.

`diagnostic.json` contains file/code hashes, environment versions, fixed rules,
scene calibration, per-frame motion/feature matches, unchanged raw predictions,
per-paw detector observations, 2D proximity diagnostics, states, candidate events,
and extraction/abstention reasons. The JSON is written without nonfinite values.
`diagnostic.jpg` overlays source frames 0, 30 and 59 with the texture reference,
background check region, actor exclusions, actual matches and raw model paws.
It is a diagnostic image, not a review interface or a contact annotation.

Dog02 human annotations are non-independent and are neither automatic inputs
nor a validation set here. Scene coordinates are explicit image calibration,
not video-specific threshold tuning. The one pilot is descriptive; do not adjust
the gates to manufacture events or optimize performance on Dog02.

## Tests

```bash
.venv-canine-v2/bin/python -m pytest -q \
  tests/test_ground_evidence.py tests/test_gait_events.py \
  tests/test_gait_cycles.py tests/test_gait_metrics.py \
  tests/test_gait_integration.py tests/test_gait.py tests/test_scientific_metrics.py
python -m pytest -q tests/test_gait_event_review.py
```

The review HTTP tests require a temporary localhost socket, which may require
running outside the sandbox. No test here needs training or new pose inference.
