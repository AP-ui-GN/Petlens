# Pose check

This is a visual check of the dog detector and the pose head. It is not a
clinical validation.

```bash
python scripts/check_pose_backend.py path/to/dog-walk.mp4 --out outputs/pose-check/
```

The script writes eight frames. Each point is labeled with the checkpoint
name and its confidence. A point under the score cutoff is an open circle
and is not connected. The current head is COCO-17. Channel 4 is the right
ear. The base of the tail is not in the output, so the script does not
score a nose-to-tail distance.

On the side-view clip used here, the review script reported the right ear
91.0 px from the nose and 352.6 px from the left hip. That is why an AP-10K
label on channel 4 drew `root_of_tail` on the head.

What matches the body on the drawn frames: the dog box, the nose on the
snout, the eyes and ears on the head, the shoulders on the withers, and the
leg joints on the legs, with the ankles below the hips. A person at the
left edge is not the selected box.

What does not match a dog skeleton: there is no neck and no base of the
tail, so the tail has no point. Left and right stay close together on this
side view (median eyes 11.1 px apart, ears 5.4 px apart). Some rear-leg
links cross. `left_knee` on the first frame scored 0.38. Renaming channels
to satisfy a nose-farther-than-eyes rule would put the wrong name on a
coordinate the checkpoint already labeled.

Do not commit the video or the images. `outputs/` and `validation_clips/`
are gitignored.

Labeled clips, when you have them, go in `validation_clips/` with
`validation_clips/labels.csv`. Columns: `file,label,source,license,notes`.
`label` is `normal`, `mild`, or `significant`. See `TESTING.md`.
