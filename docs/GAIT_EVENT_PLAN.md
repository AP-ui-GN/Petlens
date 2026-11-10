# Milestone 2 planning checkpoint — November 10, 2026

Planning is complete; the gait-event detector is not implemented. Existing
position peaks remain kinematic candidates, with zero verified complete cycles.
This preserves the Day 2 decision after architecture.txt was replaced by later
session reports.

The selected future approach is ground-relative paw motion and clearance:

1. Register visible ground texture between original frames, masking dogs and
   people. Reject unreliable registration or unsupported moving surfaces.
2. Measure ground-relative paw displacement and projected clearance from an
   explicitly supplied ground band, using the existing body reference for scale.
3. Use consecutive supporting observations and hysteresis to distinguish
   contact-supported, swing-supported, and unknown states.
4. Emit candidate contact/lift-off transitions. Form candidate strides only
   within one sufficiently certain physical identity segment. Missing paws,
   uncertain identities, or unsupported ground evidence reset state to unknown.

Preserve raw observations. Body-relative motion alone does not establish contact.
Use one shared configuration frozen on synthetic cases, without tuning to
Dalmatian, Dog02, or Husky. This checkpoint adds no algorithm implementation.

Human references use visual contact, not force or weight bearing. Initial contact
requires last definitely airborne / first definitely contacting frames; lift-off
requires last definitely contacting / first definitely airborne frames. Next
contact must concern the same physical paw. Unknown boundaries stay missing.

Complete Milestone 3 before detector implementation: review originals without
predictions or previous labels, preserve exposure declarations and uncertainty,
and obtain at least three adjudicated complete strides across two source videos.
Seek independent review and reconcile disagreements before scoring. Current
written Dog02 observations are non-independent drafts and establish zero complete
strides. See PETLENS_PROGRESS.md for the exact next task and remaining evidence.

Future evaluation should match events one-to-one by type and physical identity,
using a fixed alignment per segment. Report precision, recall, source-frame/time
boundary error, abstention, and reviewed coverage. Unreviewed frames are not
negative labels. No current evidence establishes clinical validity.
