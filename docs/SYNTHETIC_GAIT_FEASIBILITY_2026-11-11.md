# Synthetic contact data feasibility — 11 November 2026

**CONDITIONAL.** A small mechanics/contact-label pilot is credible; commercially
useful canine training sequences are not ready. Do not allocate another sprint
day to simulation until the anatomical/export gap below has a bounded solution.
No simulator, dataset or generated training examples were installed/downloaded
or implemented in this investigation. No additional model was trained.

## Best candidate: MuJoCo + dm_control quadruped

[MuJoCo](https://github.com/google-deepmind/mujoco/blob/main/LICENSE) and
[dm_control](https://github.com/google-deepmind/dm_control/blob/main/LICENSE)
are Apache-2.0. This is permissive code licensing, with notice/license and
modification requirements, not certification of canine biomechanics. The
inspected [quadruped XML](https://github.com/google-deepmind/dm_control/blob/main/dm_control/suite/quadruped.xml)
uses primitive geometry; its common materials/skybox are procedural. No external
dog mesh, commercial animation, dataset or learned controller is cleared by
those licenses. Stay with these repository assets for an initial mechanics test.

The [task implementation](https://github.com/google-deepmind/dm_control/blob/main/dm_control/suite/quadruped.py)
exposes four named toes, positions, walking/running speed targets and a fixed
control interval. These are task/reward definitions, not a supplied stable dog
walking controller. Body dimensions and speed objectives could be varied, but
plausible gait or proportional variants would need verification; neither follows
automatically from changing parameters.

[MuJoCo contact-force access](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-contactforce)
provides solver forces. A future definition should require a named paw/floor
collision with positive normal support force above a documented tolerance;
near-zero/ambiguous values remain masked. Log all substeps, hysteresis/tolerance,
geom IDs and timestamps. Liftoff/touchdown are transitions of that defined state,
not changes guessed from pixels. Fixed timestep and seed provide reproducible
timing within a pinned environment. Compliant contact remains a model of support,
not real paw-pressure ground truth. A scripted foot near the floor or a collision
candidate alone is not sufficient contact evidence.

**Specific blocker:** this primitive quadruped has no canine head, eyes, nose,
neck or tail-root schema. It cannot directly satisfy our body-reference and
17-joint AP-10K contract. Do not manufacture those joints or relabel solver world
coordinates as saved RTMPose observations. Rendered pose-estimator outputs would
need a suitable licensed canine rig and validated camera/joint mapping; direct
simulator coordinates require a separately versioned, explicit synthetic adapter.
Missing scores must not be fabricated as measured RTMPose confidence. Preserve
the existing real-data adapter and training architecture.

Smallest future proof of concept: one 2–4-second four-foot support/lift sequence,
logging mechanics-derived states and positions, with one repeatability check.
It is a contact-logger demonstration, not a canine training corpus. Only after
that succeeds consider a single small walking sequence with licensed canine
anatomy and truthful feature mapping. Keep simulation output in a distinct
synthetic provenance namespace; never approve it as human real-dog ground truth
or mix it into the real evaluation cohort.

Engineering estimate, not a measured result: 2–4 hours for the mechanics logger
once an engine is authorized/available; suitable canine assets, walking control
and the feature bridge could take days. **Stop after four engineering hours** if
repeatable contacts or an honest landmark mapping cannot be demonstrated. Do not
train a new locomotion policy, build a simulator, or expand into mass generation
to rescue the pilot. Real footage remains necessary to test domain transfer.

## AI-generated videos: no contact-label source

Photorealistic dog videos may be useful presentation material, but appearance
does not establish support force, stable limb identity or correct timing. Paw
sliding, changing anatomy, identity swaps and physically inconsistent cycles
are failure modes to screen, not measured error rates from this investigation.
A video without independently defined contact mechanics supplies no trustworthy
CONTACT/AIRBORNE labels. Do not derive truth from the same model being trained.

[Runway's commercial-use help](https://help.runwayml.com/hc/en-us/articles/21668707517587-Can-I-use-the-content-I-made-in-Runway-for-commercial-purposes)
permits commercial output use subject to its agreement. Its
[October 23, 2026 terms](https://runway.com/terms-of-use), section 5.2, restrict
using services/outputs to train or improve similar or competitive products.
That is not a blanket ban on every classifier, but output ownership alone does
not clear this training use or third-party input assets. Written clarification
would be needed if proceeding. Even permission would not solve missing contact
truth. No generated videos were commissioned or treated as training labels.

## Existing data: what it actually supplies

| Source | Evidence type | Commercial-training decision |
| --- | --- | --- |
| Proposed MuJoCo primitive pilot | Mechanically defined support contacts, if logged/verified | Permissive code/assets inspected; not yet canine-compatible data |
| [DigiDogs](https://cvssp.org/data/DigiDogs/) | Synthetic GTA-V videos, skeletons and 2D/3D pose; not documented force-based contact truth | Official data page restricts original images/data to non-commercial research; reject for this commercial corpus |
| [3DDogs](https://cvssp.org/data/3DDogs/) | Real multimodal pose/mocap and pressure-mat capture | Contact-related evidence may be useful scientifically, but official data page is non-commercial research only; not cleared for PetLens training |
| AI-generated video | Appearance without trustworthy contact mechanics | Not an approved contact-label source, independently of output-use rights |

Code licenses, rig/texture licenses, motion-data terms, controller weights and
output-training permission must be checked separately. No verified ready-made,
commercially usable canine force-contact dataset emerged in this bounded check.
Public download availability does not change that result.

For the next session, prioritize a different real dog's rights-cleared contiguous
labeling clip. The synthetic option deserves at most the four-hour conditional
pilot above, not a new November infrastructure workstream. Keep roughly equal
attention on gait evidence and Motion Studio product work.
