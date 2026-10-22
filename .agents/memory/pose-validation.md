---
name: Pet pose validation
description: The dog detector and animal pose model are unproven on pet dogs until a labeled set is measured.
---

The current pose path uses a dog detector and `usyd-community/vitpose-plus-base`.
Dataset index 3 selects a backbone expert. The only keypoint head in that
checkpoint is the 17-channel COCO head. Channel 4 is the right ear. On one
side-view frame the right ear sat beside the nose, not at the base of the
tail. Stride length stays unmeasured because this head has no neck and no
base of the tail. Do not treat a symmetry number from this head as validated.

**Why:** Pose quality on pet dogs is unproven until a labeled set is measured.
The channel names match the checkpoint. That naming check is not a validation.

**How to apply:** Keep missing measurements null. Do not mix pipelines in one
trend series. Say ask a veterinarian when a measured change is concerning.
Do not name a condition.
