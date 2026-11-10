# Dog02 written observations — proposal awaiting confirmation

This is a draft derived from the user's prompt and the saved exported review
`reviews/review-d684d28c840a475ba7833f1c045d2504.zip`. Live browser storage was
not accessed. The saved ZIP and all original A/B descriptions are unchanged.
No final export or browser import has been performed.

`dog02-reviewer-1-written-observations-v1.review.json` passes the existing
review validator. Its companion `.proposal.json` contains typed uncertainty
windows, identity statements, provenance, and every proposed before/after change.
The existing review schema stores uncertain timing windows in notes; the
companion file makes their meaning explicit without changing the viewer/schema.

| Paw | Frame(s), source time | Proposed observation | Evidence limit |
| --- | --- | --- | --- |
| A/B | 0, 0 s | Observation started; no event | Does not establish support state |
| A | 19, 1.583333 s | Human-reported touchdown/contact | Last definitely airborne frame missing |
| A | 55, 4.583333 s | Possible lift-off | Possible timing only; no definite support state |
| A | 56, 4.666667 s | Human-confirmed airborne observation | Exact transition may have been at 55; last definitely contacting missing |
| B | 23, 1.916667 s | Human-reported lift-off/airborne | Last definitely contacting frame missing |
| B | 52–59, 4.333333–4.916667 s | Human reports touchdown in this interval; 52 possible | No exact definite-contact frame; endpoints are not support-state brackets |
| A/B | 0–59 | Human-reported continuous physical identity | No anatomical mapping or bulk visibility/support-state labels |

All confirmations above are human reports, not automated verification.

**Proposed corrections requiring approval:**

- Saved declaration `no_prior_exposure` -> `prior_exposure`, following the
  user's explicit current statement. Reviewer `reviewer-1` is retained.
- Saved frame-0 airborne states -> unreviewed, because the prompt only
  establishes observation start. Original visible/start labels are retained.
- Saved B23 contacting -> airborne, following the written lift-off observation.
- Saved B52 contacting -> uncertain, following the written timing uncertainty.
- Preserve A19 contacting, A56 airborne, A51 visibility and all other existing
  observations except the explicit proposed changes recorded in the companion.

No visibility or continuity fields were filled across the sequence. The
sequence-level continuity statement is preserved separately. Original
pawDescriptions remain byte-for-byte equivalent strings in the derived draft.
The review schema's legacy blind/session exposure flags are retained for
compatibility; `independenceDeclaration=prior_exposure` and the validator's
`independenceDeclared=false` identify these observations as non-independent.

**Complete strides established: zero.**

A has contact at 19 followed by an airborne observation at 56, but lacks:

- Last definitely airborne frame before contact at 19.
- Last definitely contacting frame before lift-off.
- Both boundaries of the next contact of A after lift-off.

B has a lift-off observation at 23 and an uncertain later touchdown window, but lacks:

- Both boundaries of the initial contact before lift-off at 23.
- Last definitely contacting frame before lift-off at 23.
- Both definite boundaries of the subsequent contact; 52–59 is only a timing window.

Intervening visibility and support-state evidence also remains unreviewed where
not already explicitly recorded. The written identity statements do not supply it.

Both partial stride assertions have status `uncertain`. Missing boundaries are
null. Neither frame 0 nor frame 59 is invented as an event boundary. The
three-stride/two-video requirement is not met.

Validation: existing validator accepted the draft, counted zero complete strides,
and returned independenceDeclared=false. Source ZIP member checksums, video hash,
and source-manifest linkage were verified. No pose inference or gait changes ran.

Do not finalize, merge, or import this proposal until the user confirms it.
