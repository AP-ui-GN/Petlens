# Proposed owner-authorized contact training policy v1

Status: PROPOSED. Implementing support does not approve this policy or any data.

The two unexposed reviewers requirement originates in the project's
CONTACTVISION_READINESS_AUDIT.md annotation protocol and
prepare_contact_sequences._labels. No external mandate for that reviewer count
was identified in the project records. It remains unchanged for strict mode.

An owner may separately authorize `exploratory_train_only` for a bounded contact
state optimization experiment. This permits one dog, sparse approved labels on
selected paws, one honestly declared (possibly previously exposed) reviewer,
and source-movie PTS without native camera attestation. It permits neither
independent validation claims nor accurate event-timing claims. No validation
or test frames may enter the experiment. Related sources inherit the same dog
and provenance group. Unknown dog identity, unclear rights, missing physical
identity, or unapproved labels remain blockers.

Approval must be a separate hash-checked JSON record, signed by name, owner
role, date and evidence. It must explicitly accept each scope below, bind the
policy's SHA256 and the exact source, predictions, frame manifest, label
sidecar and rights-evidence hashes, identify the dog, and authorize training.

Required scope flags: trainOnly, sparsePaws, sourceMovieTiming,
singleExposedReviewer, noGeneralizationClaims. Each must be explicitly true.
Rights must be cleared with retained attribution and an identified approver.
Each selected observation needs its own signed approval. The original reviewer
and exposure declaration remain recorded. A signature is an attributable human
attestation, not a cryptographic identity verification service.

Physical paw names must map explicitly to LF/RF/LH/RH with named human evidence.
Only mapped paws may be supervised. Mapping must respect fore/hind roles and
be one-to-one. A signed identity span certifies visible physical continuity,
not contact state. It cannot fill UNKNOWN contact interiors. Source labels
must be definite, conflict-free CONTACT/AIRBORNE assertions with visible paw
evidence; provisional, disputed, UNKNOWN and unreviewed records always mask out,
even if an approval entry incorrectly requests their inclusion. Unreviewed
physical identities remain unverified. Existing annotations are never rewritten.

Runs are CPU deterministic under a recorded configuration, limited to at most
100 epochs, 32 windows, 3,200 optimizer steps and 128 frames per window. Only
training metrics and a final checkpoint are saved. There is no validation-based
selection or test score. All results/checkpoints are marked exploratory,
train-only and unvalidated. Source/native timing distinctions remain explicit.
Strict-mode readiness, independent review and multi-dog evaluation gates stay
unchanged. An exploratory prepared dataset is incompatible with strict mode.

Owner authorization must be provided separately for each run's inputs. A new
policy text, source, annotation, or rights-evidence hash requires new approval.
