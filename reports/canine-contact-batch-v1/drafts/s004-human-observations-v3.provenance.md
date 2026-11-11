## Source and reviewer

Dataset: `gait-s004`

Source: `reports/canine-contact-batch-v1/frame-manifest.json`

These observations come from the same previously exposed human reviewer. Do not describe them as independent ground truth.

## PART 1 — PRESERVE V2 EVENT RANGES

Hind A:
- Frames 16–19: Transition to AIRBORNE.
- Frames 44–49: Originally reported TOUCHDOWN.

Hind B:
- Frames 7–8: TOUCHDOWN.
- Frames 50–54: Transition to AIRBORNE.

Front C:
- Frames 5–10: TOUCHDOWN.
- Frames 47–49: Transition to AIRBORNE.

Front D:
- Frames 8–12: Transition to AIRBORNE.
- Frames 35–40: TOUCHDOWN.

Preserve these as uncertain event ranges, not exact event timestamps.

## PART 2 — NEW HUMAN FRAME OBSERVATIONS

### FRONT C

- Frame 4: UNKNOWN. Video quality prevents determining contact.
- Frame 11: CONTACT, high confidence. Physical identity confirmed.
- Frame 46: CONTACT, approximately 80% confidence.
- Frame 50: AIRBORNE, 100% confidence.

### FRONT D

- Frame 7: UNKNOWN. Part of paw appears to touch ground, but frame quality makes assessment unreliable.
- Frame 13: AIRBORNE, moderate confidence. Provisional.
- Frame 34: UNKNOWN. Paw extremely close to ground; possible contact.
- Frame 41: CONTACT, 95% confidence.

### HIND A

- Frame 15: CONTACT, 80% confidence. Part of paw appears to touch ground.
- Frame 20: AIRBORNE, 100% confidence.
- Frame 43: CONTACT, described as "pretty confident." No numerical confidence given.
- Frame 50: CONTACT, 100% confidence.

IMPORTANT: Frame 43 conflicts with the originally reported touchdown range of 44–49. Preserve both observations and explicitly flag the inconsistency. Do not silently change the original event range or infer an exact touchdown frame.

### HIND B

- Frame 6: UNKNOWN. Paw extremely close to ground.
- Frame 9: CONTACT, described as "very confident."
- Frame 49: CONTACT. Part of paw visibly touching ground; no numerical confidence given.
- Frame 55: AIRBORNE, 100% confidence.

## Encoding and evidence limits

V3 adds exactly these 16 human observations to V2's eight unchanged event
intervals. It supersedes V2 as the working draft, preserving all V1/V2 files.
The 16 observations comprise 11 non-provisional definite human state assertions,
one provisional AIRBORNE assertion (D13), and four explicitly reviewed UNKNOWN
states (C4, D7, D34, B6). "Definite" denotes a human state assertion, not training
approval, independent verification, or an invented confidence threshold. A43 is
retained as a definite human CONTACT assertion with an unresolved conflict.

The existing schema has no confidence/provisional field. Confidence and status
are stored in the frame sidecar. D13 uses core `supportState=uncertain` while
its reported AIRBORNE state and exact "moderate confidence. Provisional." wording
remain in the sidecar and core notes. It is not a binary training target.

The remaining 224 paw-frame slots are `unreviewed`, explicitly distinguishing
them from the four reviewed UNKNOWN observations. V2's UNKNOWN placeholders
were not completed frame reviews and are not promoted into new observations.
No intervening support, visibility or identity flags are filled.

For the 11 definite frame assertions, `visibility=visible` records the human's
direct visible support-state report, and `continuity=continuous` carries the
same human's V2 declaration of tracking all physical paws throughout. Only C11
has an additional explicit frame-specific physical-identity confirmation in
this task. This encoding does not independently verify continuity or establish
continuity/visibility/support on intervening unreviewed frames. D13 retains
uncertain support; the four UNKNOWN records retain uncertain visibility and
unreviewed continuity. Each sidecar record identifies these evidence sources.

Confidence percentages are transcribed only where supplied. "Approximately"
is retained for C46's 80%; no percentage is invented for high confidence, moderate
confidence, "pretty confident," "very confident," UNKNOWN or B49. Percentages
are reviewer self-reports, not calibrated probabilities or loss weights.

The A43 CONTACT assertion and A touchdown 44–49 remain separate unresolved
evidence. An additional unreported lift-off and touchdown could make both
observations possible; no such events are invented. The discrepancy is not
silently resolved by moving the event, deleting A43, or filling a contact span.

Prior footage and annotation exposure stay explicit. The V3 browser session ID
`s004-requesting-user-written-v3` identifies the same human as the V1/V2 IDs,
with separate storage. `independenceDeclaration=prior_exposure` remains in the
core draft. Legacy required viewer fields (`blind=true`, `modelExposed=false`,
`previousLabelsExposed=false`) do not assert lifetime non-exposure; the sidecars
retain the actual history. No model contact guesses are used. Anatomical
left/right mapping and the exact Front C reference frame remain unresolved.
