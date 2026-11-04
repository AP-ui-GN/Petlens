# RTMPose neck-threshold sweep for the neck + tail-root reference

Data source: `tmp/rtmpose-test/full-video/rtdetr-rtmpose-full-video.json` (165 frames; unchanged original predictions).

Jump definition used in all counts (same as earlier experiments):
- Compute the Euclidean distance between consecutive normalized right-back-paw positions.
- Only count it when both frames are usable, the right-back-paw score is at least 0.80 in both frames, and the distance exceeds 0.35 reference lengths per frame.
- This is a suspicious jump in the reference geometry, not a new criterion.

Method B tested: neck threshold sweep with the tail-root threshold fixed at 0.80.
Method A baseline: shoulders + hips, all four landmarks at 0.80.

| Method / neck threshold | Usable frames / 165 | Longest uninterrupted usable run | Median neck-to-tail-root length change* | 95th-percentile change* | Suspicious jumps |
|---|---:|---:|---:|---:|---:|
| Method A (shoulders + hips) | 142 | 15 | 2.59% (1.72 px) | 9.06% (6.28 px) | 0 |
| Method B, neck >= 0.65 | 160 | 56 | 1.22% (1.10 px) | 3.72% (3.52 px) | 0 |
| Method B, neck >= 0.70 | 156 | 55 | 1.22% (1.10 px) | 4.09% (3.67 px) | 0 |
| Method B, neck >= 0.75 | 131 | 54 | 1.36% (1.27 px) | 4.82% (4.02 px) | 0 |
| Method B, neck >= 0.80 | 75 | 15 | 1.59% (1.62 px) | 9.14% (7.42 px) | 0 |

*Frame-to-frame change is computed on consecutive usable frames only, using the same percent-of-previous-length convention used earlier in the body-reference comparison (with absolute px change shown in parentheses).

Summary:
- Lowering the neck threshold from 0.80 to 0.70 adds 81 usable frames (75 -> 156) while keeping geometry stability strong and suspicious jumps at zero.
- Method B at 0.70 gives the best practical trade-off: ~94% usable coverage, a 55-frame run, and a compact median length change (~1.2%) with no jump warnings.
- Method A remains a conservative fallback with 142 usable frames and no jumps, but it is a less informative body reference than neck + tail root.
- At 0.80, Method B is too sparse for a real-time or tracking-heavy workflow: only 75/165 usable frames and a 15-frame max run.

Recommendation:
- Use Method B with a neck confidence threshold of 0.70 and tail-root fixed at 0.80 as the default choice for this dataset.
- Keep Method A as the fallback or sanity-check baseline when the neck is weak or a more conservative body reference is preferred.

Why 0.70:
- It preserves almost all usable data without a meaningful increase in suspicious geometry jumps.
- It avoids the sharp coverage collapse seen at 0.80 while still keeping the neck from being overly permissive.
- It is a better body-reference match than shoulders + hips for a torso-length analysis, while still being robust enough for continued tracking.
