# Full-video RT-DETR + RTMPose hind-leg consistency report

- Input: `tmp/rtmpose-test/full-video/rtdetr-rtmpose-full-video.json`
- Frames: 165 at 29.97 FPS (5.47 seconds).
- Successful dog detections: **161/165**.
- Frames with suspicious paw measurements: **20** (12.1%).
- Frames passing all usability checks: **134/165**.
- Frames with no dog detection: 4, 110, 111, 116.
- Possible left/right identity warnings: **0**.
- Frames with suspicious paw measurements: 0, 1, 12, 21, 22, 23, 24, 34, 44, 45, 55, 67, 77, 100, 122, 134, 148, 162, 163, 164.
- Longest uninterrupted usable sequence: **11 frames** (frames 56–66, 0.33 seconds from first to last).
- Mean detector time: 2.1564 seconds/frame; mean pose time on detected frames: 0.1874 seconds/frame.

## Rules used

- Low raw score: below 0.80 for any hind-leg hip, knee, or back paw. A low-confidence back paw counts as a suspicious paw frame.
- Sudden change: more than 0.35 torso lengths between adjacent frames for a hind-leg hip, knee, or back paw. Both frames are marked for the usable-run calculation; a back-paw jump counts as a suspicious paw measurement.
- Possible identity ambiguity: prior hind paws within 0.25 torso lengths, both paws then move more than 0.35, and swapped chains have movement cost no more than 1.15 times the unchanged-label cost. This is only a warning.
- Usable frame: dog detected, all six hind-leg points and raw scores present, all six raw scores at least 0.80, and no low-score, jump, or identity warning on that frame.

Raw model scores are not calibrated probabilities. These thresholds are experimental screening rules, not validated gait-quality criteria. No points were filled in, smoothed, or relabeled.

## Uninterrupted usable sequences

- Frames 2–3: 2 frames (0.03 seconds from first to last).
- Frames 5–10: 6 frames (0.17 seconds from first to last).
- Frames 13–20: 8 frames (0.23 seconds from first to last).
- Frames 25–33: 9 frames (0.27 seconds from first to last).
- Frames 35–43: 9 frames (0.27 seconds from first to last).
- Frames 47–54: 8 frames (0.23 seconds from first to last).
- Frames 56–66: 11 frames (0.33 seconds from first to last).
- Frames 68–76: 9 frames (0.27 seconds from first to last).
- Frames 78–87: 10 frames (0.30 seconds from first to last).
- Frames 89–99: 11 frames (0.33 seconds from first to last).
- Frames 101–109: 9 frames (0.27 seconds from first to last).
- Frames 112–115: 4 frames (0.10 seconds from first to last).
- Frames 117–121: 5 frames (0.13 seconds from first to last).
- Frames 124–131: 8 frames (0.23 seconds from first to last).
- Frames 133–133: 1 frames (0.00 seconds from first to last).
- Frames 135–139: 5 frames (0.13 seconds from first to last).
- Frames 141–147: 7 frames (0.20 seconds from first to last).
- Frames 149–159: 11 frames (0.33 seconds from first to last).
- Frames 161–161: 1 frames (0.00 seconds from first to last).

## Frame-by-frame flags

### Frame 0
- Low-confidence left_hip (raw score 0.726 < 0.80).
- Low-confidence left_knee (raw score 0.753 < 0.80).
- Low-confidence left_back_paw (raw score 0.599 < 0.80).

### Frame 1
- Low-confidence left_hip (raw score 0.751 < 0.80).
- Low-confidence left_knee (raw score 0.683 < 0.80).
- Low-confidence left_back_paw (raw score 0.410 < 0.80).

### Frame 4
- RT-DETR did not detect a dog.

### Frame 11
- Low-confidence left_hip (raw score 0.786 < 0.80).

### Frame 12
- Low-confidence left_hip (raw score 0.631 < 0.80).
- Low-confidence left_knee (raw score 0.676 < 0.80).
- Low-confidence left_back_paw (raw score 0.591 < 0.80).

### Frame 21
- Sudden right back_paw change from frame 21 to 22 (0.527 torso lengths).

### Frame 22
- Low-confidence left_hip (raw score 0.783 < 0.80).
- Sudden right back_paw change from frame 21 to 22 (0.527 torso lengths).

### Frame 23
- Low-confidence left_hip (raw score 0.683 < 0.80).
- Low-confidence left_knee (raw score 0.730 < 0.80).
- Low-confidence left_back_paw (raw score 0.642 < 0.80).

### Frame 24
- Low-confidence left_knee (raw score 0.795 < 0.80).
- Low-confidence left_back_paw (raw score 0.748 < 0.80).

### Frame 34
- Low-confidence left_hip (raw score 0.670 < 0.80).
- Low-confidence left_knee (raw score 0.685 < 0.80).
- Low-confidence left_back_paw (raw score 0.662 < 0.80).

### Frame 44
- Low-confidence right_back_paw (raw score 0.783 < 0.80).

### Frame 45
- Low-confidence left_hip (raw score 0.751 < 0.80).
- Low-confidence left_knee (raw score 0.714 < 0.80).
- Low-confidence left_back_paw (raw score 0.713 < 0.80).

### Frame 46
- Low-confidence left_hip (raw score 0.767 < 0.80).
- Low-confidence left_knee (raw score 0.793 < 0.80).

### Frame 55
- Low-confidence left_hip (raw score 0.751 < 0.80).
- Low-confidence left_knee (raw score 0.781 < 0.80).
- Low-confidence left_back_paw (raw score 0.763 < 0.80).

### Frame 67
- Low-confidence left_hip (raw score 0.772 < 0.80).
- Low-confidence left_knee (raw score 0.701 < 0.80).
- Low-confidence left_back_paw (raw score 0.561 < 0.80).

### Frame 77
- Low-confidence left_hip (raw score 0.732 < 0.80).
- Low-confidence left_knee (raw score 0.798 < 0.80).
- Low-confidence left_back_paw (raw score 0.624 < 0.80).

### Frame 88
- Low-confidence left_hip (raw score 0.778 < 0.80).

### Frame 100
- Low-confidence left_hip (raw score 0.780 < 0.80).
- Low-confidence left_back_paw (raw score 0.682 < 0.80).

### Frame 110
- RT-DETR did not detect a dog.

### Frame 111
- RT-DETR did not detect a dog.

### Frame 116
- RT-DETR did not detect a dog.

### Frame 122
- Low-confidence left_back_paw (raw score 0.798 < 0.80).

### Frame 123
- Low-confidence left_knee (raw score 0.795 < 0.80).

### Frame 132
- Low-confidence left_hip (raw score 0.759 < 0.80).
- Low-confidence left_knee (raw score 0.773 < 0.80).

### Frame 134
- Low-confidence left_back_paw (raw score 0.705 < 0.80).

### Frame 140
- Low-confidence left_hip (raw score 0.799 < 0.80).

### Frame 148
- Low-confidence left_hip (raw score 0.750 < 0.80).
- Low-confidence left_knee (raw score 0.660 < 0.80).
- Low-confidence left_back_paw (raw score 0.621 < 0.80).

### Frame 160
- Low-confidence left_hip (raw score 0.798 < 0.80).

### Frame 162
- Low-confidence left_knee (raw score 0.749 < 0.80).
- Low-confidence left_back_paw (raw score 0.657 < 0.80).

### Frame 163
- Low-confidence left_back_paw (raw score 0.793 < 0.80).

### Frame 164
- Low-confidence left_back_paw (raw score 0.627 < 0.80).
- Low-confidence right_knee (raw score 0.797 < 0.80).
- Low-confidence right_back_paw (raw score 0.706 < 0.80).
