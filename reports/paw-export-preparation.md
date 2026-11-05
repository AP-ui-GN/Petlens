# Dalmatian export preparation

> Superseded after the user explicitly authorized reuse of their mapping and continuity confirmation. Validated export: `paw-annotation-data-v2/dalmatian-reviewed.zip`; current counts and limitations: `paw-annotation-data-v2/export-summary.json`. The earlier blocked status below is historical.

Status: blocked; no anatomical export generated. The complete proposed mapping,
79 original coordinates, exclusions, provenance hashes and blockers are in
`paw-export-preparation.json`. No source annotations or browser decisions changed.

Final proposed mapping for source frames 46–90 inclusive:

| Physical paw | Anatomical identity |
| --- | --- |
| A | Right hind (`right_back_paw`) |
| B | Left hind (`left_back_paw`) |

The source-backed preview passes validation and includes 79 visible annotations
across 42 frames. All 79 coordinates match the original labels exactly. The 11
nonvisible slots stay excluded: B at 61; A at 81 and 83; both at 84, 86 and 87;
B at 85 and 88. No hidden coordinates were inferred.

## Why preview fails in the browser

Preview calls the full export validator before selecting bulk targets. A changed
coordinate/status or verified identity requires nonblank per-record `reviewer`
and `evidence`. Verified identities also require `landmarkConfirmed` and
`continuityConfirmed`. Bulk form values apply only to eligible untouched records;
they do not complete earlier edits or decisions. The browser draft includes both
datasets, so a record in either dataset can block preview.

No saved V2 review draft was found in the workspace. The on-disk accepted
anatomical review list is empty; the source-backed seed has no incomplete edited
or verified records. The exact incomplete browser records are therefore unknown.
The source names Sudar as physical annotator; this does not establish the
anatomical reviewer. The existing reviewer-provided continuity statement covers
frames 75–90 and is not independent anatomical verification.

## Finish using existing decisions

1. Restart `python -m training.review_paw_annotations` and reload the review page.
   Download the existing draft as a backup. Browser storage remains intact.
2. Choose **Check incomplete reviews** to list exact dataset/frame/paw records and
   missing fields; **Download validation report** saves the read-only result.
3. Complete only missing fields with actual reviewer information and evidence.
   Preserve existing decisions, uncertainty, coordinates and review provenance.
   If the information is unavailable, keep the export blocked.
4. Preview again. Confirm the mapping above, the visible paw-tip landmarks and
   physical continuity for the displayed targets, using the actual anatomical
   reviewer and evidence. Existing reviews and uncertain records stay excluded;
   counts can be lower than 79 when the browser already has decisions.
5. Apply the confirmed mapping, then **Validate & download versioned export**.
   Both apply and export rerun server validation; failures produce no export ZIP.

Alternatively, provide the downloaded existing draft for offline diagnosis with
`--draft ... --diagnostics-output ...`. Do not substitute a fresh draft for the
browser's reviewed data, or attribute anatomical decisions to the original
physical annotator without evidence.
