# Proposed identity-neutral exploratory addendum v1

UNSIGNED PROPOSAL. This does not grant owner authorization or training approval.
The existing EXPLORATORY_CONTACT_POLICY.md and all its rights, review, source,
dog, timing and bounded train-only requirements remain applicable, except for
the explicitly scoped alternative to anatomical mapping below.

The owner may authorize `identity_neutral_front` supervision of one tracked
physical front paw in one source clip and one physically continuous reviewed span.
The anatomical side stays UNKNOWN. The physical output is bound to that paw,
source video SHA256, dog grouping, dataset and frame span. It cannot be used as
LF, RF, an arbitrary C from another clip, or the other front paw.

One new linear readout uses the existing Transformer encoder representation.
No LF/RF outputs are combined, assigned by loss, or supervised. The four-paw
anatomical head receives no gradient and remains unused. Input features stay
69-channel AP-10K. Both front-paw observation channels must be available for
supervised frames because neither has been matched to the tracked paw; this
is a conservative input-quality gate, not anatomical identification. A signed
physical continuity span is also required. Endpoint visibility must be supported
by the original human observations. Visibility or contact states are not filled
across the intervening frames; contact interiors remain masked unless individually
observed and approved.

The owner must sign the base policy scopes plus `identityNeutralOutput=true`,
bind both policy hashes and the exact physicalOutput specification, and approve
the two selected observations, physical continuity, reuse rights/attribution,
and conservative source/dog grouping. Prior reviewer exposure remains explicit.
The human continuity report may be recorded without falsely marking it approved.

This is clip-bound representation fitting and can memorize source, frame phase
or background pose patterns. It supplies no evidence that the model can locate
an unknown physical paw in another video, learn reliable temporal contact, or
generalize. It does not establish event timing, anatomical accuracy, clinical
validity or independent evaluation. Only synthetic execution is authorized until
the owner separately signs the real-data request. Strict training is unchanged.
