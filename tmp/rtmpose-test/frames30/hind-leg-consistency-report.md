# Experimental hind-leg temporal consistency report

- Input: `tmp/rtmpose-test/frames30/rtmpose-30-raw-predictions.json`
- Frames: 67–96 (30 consecutive frames)
- Coordinates: hip, knee, and back paw positions relative to each frame's torso center, normalized by shoulder-to-hip distance.
- Predictions and labels are unchanged; this report only flags possible issues.

## Rules used

- Low confidence: raw score below 0.80. These are raw model scores, not calibrated probabilities.
- Sudden change: a same-label joint moves more than 0.35 torso lengths in one frame.
- Possible identity ambiguity: prior hind paws are within 0.25 torso lengths, both same-label paws then move more than 0.35, and swapping the current left/right chain assignments gives a total movement cost no more than 1.15 times the unchanged-label cost. This is a warning, not an instruction to swap labels.

## Flags

### Frame 67
- Low-confidence left_knee (raw score 0.749 < 0.80).
- Low-confidence left_back_paw (raw score 0.662 < 0.80).

### Frame 77
- Low-confidence left_back_paw (raw score 0.743 < 0.80).

### Frame 87
- Low-confidence left_back_paw (raw score 0.632 < 0.80).
- Low-confidence right_back_paw (raw score 0.665 < 0.80).

### Frame 88
- Low-confidence left_back_paw (raw score 0.765 < 0.80).

### Frame 89
- Low-confidence left_back_paw (raw score 0.792 < 0.80).

### Frame 90
- Low-confidence left_back_paw (raw score 0.665 < 0.80).

### Changes between consecutive frames

- Frames 90 → 91: left back_paw moved 0.402 torso lengths.
- Frames 90 → 91: right back_paw moved 0.516 torso lengths.
- Frames 90 → 91: **possible left/right identity ambiguity**. The prior paws were 0.206 body lengths apart; same-label paw jumps were 0.402 (left) and 0.516 (right). The unchanged-label chain cost was 1.533; the hypothetical swapped cost was 1.398. No swap was applied.

## Interpretation note

Thresholds are simple experiment heuristics, not validated gait or pose quality criteria. A low score or jump means a person should review that frame; it does not prove a joint is wrong. Occlusion can make the two hind-leg labels ambiguous.
