# DogReID-1553 investigation — 2026-11-03

Selective video retrieval is feasible and was demonstrated. This bounded screen did **not** establish five high-quality lateral walking videos: **zero strict passes; two review-only leads** from 200 distinct-dog previews and 17 retrieved videos. Do not import either lead into training yet. This is a sample result, not a claim that the remaining dataset has no suitable footage.

Open [comparison.html](comparison.html) for actual extracted frames and playable source clips, or [comparison.jpg](comparison.jpg) for a static sheet. The first two rows are review-only leads; the other three are explicitly rejected comparisons. [screened-videos.csv](screened-videos.csv) documents all 17 videos, and [preview-screening.csv](preview-screening.csv) records all 200 preview decisions.

## Verified download structure and rights

Source: [Harvard Dataverse DOI 10.7910/DVN/LVTRLG](https://doi.org/10.7910/DVN/LVTRLG), dataset numeric ID **13105717**, released **V3.2**, dataset-version ID **729962**, released 2026-05-06. Citation: Medved, Marko; Trojer, Sebastijan; Mervič, Žan; Štrumbelj, Erik (2026), *DogReID-1553: A Large-Scale Dog Re-Identification Video Dataset*, Harvard Dataverse, V3.2. Snapshot: [source/dataverse-metadata.json](source/dataverse-metadata.json).

The dataset license is **CC0 1.0**, [SPDX CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/). Dataverse's description states that participants submitted the footage with CC0 agreement, that audio was removed, and that sensitive visual information was manually obscured. These are publisher statements; this investigation does not independently audit consent. The dataset license is the source of the video rights record; do not substitute a GitHub code license.

The released version exposes five downloadable files, all marked unrestricted:

| Dataverse file | File ID | Published bytes | Details |
|---|---:|---:|---|
| Videos.zip | 13653939 | 65,539,679,181 | 65.54 decimal GB / 61.04 GiB; ZIP64 |
| Images.zip | 13652926 | 1,522,193,529 | First-frame JPEGs |
| bounding_boxes.tab | 13712995 | 698,387 | Original CSV available, 675,999 bytes |
| breeds.tab | 13765825 | 80,860 | Original breeds-1.csv available, 76,202 bytes |
| splits.tab | 13670578 | 723,090 | Original CSV available, 670,850 bytes |

Both ZIP indexes were actually read: each has **9,017 entries**, comprising **7,463 media files** and **1,554 directory entries**, across **1,553 dog identities**. Saved indexes include ZIP member names, offsets, compression methods, sizes and CRC32 values:

```text
Videos/DOG_ID/DOG_ID-VIDEO_ID.mp4
Images/DOG_ID/DOG_ID-VIDEO_ID.jpg
```

The descriptions call the images crops, but inspected JPEGs #53, #115 and #198 retain the full video-frame dimensions/background. For example #115 is 1440×1920, rather than the smaller annotation box. Treat these as first-frame previews, not guaranteed tight dog crops. Bounding boxes are **first-frame annotations only**, not temporal paw labels or per-frame dog tracks. No walking, viewpoint or hind-paw-visibility labels are supplied. Breed labels are user submitted.

The [GitHub README](https://github.com/markoMedved/DogReID-1553) describes an eight-frame sequence representation for its ReID workflow. This should not be interpreted as the length of the source MP4s: the retrieved files contain 56–872 reported frames and durations of approximately 1.87–29.10 seconds. These are real crowdsourced videos, not generated motion.

## How selective access works

An unauthenticated request to `https://dataverse.harvard.edu/api/access/datafile/13653939` redirects to a temporary signed Amazon S3 object URL. Passing a byte Range through that redirect works. The measured request for bytes **65,539,613,645–65,539,679,180** returned **HTTP 206**, an exact matching `Content-Range`, and exactly **65,536 bytes**. `Accept-Ranges: bytes` was present.

The ZIP64 central directory can then be read by offset (Videos directory: **1,703,424 bytes**), followed by only the local header and compressed data for an individual MP4. Python's standard `zipfile` handles ZIP64 offsets and deflate, and verifies member CRC32 on extraction. This is selective access to members of a single archived Dataverse file; the service does not list 7,463 independent video download endpoints. No guessed individual-file URL or external mirror was needed. Do not persist temporary signed URLs as provenance.

The first index/metadata pass transferred **4,729,253 bytes**. The first and second crop batches transferred **32,837,841** and **34,848,602 bytes**, respectively, including range/header/cache overhead. Seventeen unique source MP4s total **228,051,483 bytes**; 200 first-frame JPEGs total **52,781,249 bytes**. Network transfer is somewhat higher than retained media because central directories and 64 KiB blocks are re-read across runs. Some early multi-clip commands ended before completing the batch and were resumed; no complete archive was downloaded. These per-run figures are not presented as a full network accounting. Later bounded request records are in [source/access-audit.jsonl](source/access-audit.jsonl); logging was added after the initial retrievals.

`screen.py` refuses ignored ranges/full responses, verifies exact range lengths, caps each read at 50 MB and each invocation at 350 MB, and skips videos whose uncompressed member is over 50 MB. Existing requests and OpenCV plus the standard library are sufficient. **No dependencies were installed, RTMPose was not run, and no model was trained.**

## Review outcome

No clip is certified for all of: true walking, approximately lateral camera, both hind paws clearly distinguishable, several complete cycles, adequate temporal/spatial detail, and minimal camera motion/occlusion. No numeric camera angle is claimed without calibration, and average frame rate alone does not prove sharp, independently captured frames.

| Preview | Breed | Duration / average fps | Review result |
|---|---|---|---|
| **115** | Lurcher | 2.84 s / 29.97 | **Review-only lead.** Slow walking, full dog visible. Elevated oblique camera; ground/coat contrast and far-paw overlap are concerns; short clip, cycle count unverified. Inspect entire clip. |
| **198** | Chihuahua mix | 12.93 s / 30.00 | **Review-only lead.** Best sustained lateral-looking locomotion, inspect 0–4.5 s. Walk versus brisk trot needs human confirmation; camera follows from above; far hind paw overlaps. Exclude later curb, blur, and second-dog material. |
| 53 | English Bulldog | 7.34 s / 29.97 | Rejected: walking, but overhead viewpoint and large camera roll. |
| 170 | Beagle | 7.90 s / 30.00 | Rejected: walking/sniffing primarily seen from behind, with stops. |
| 195 | Cocker Spaniel | 1.87 s / 29.97 | Rejected: few steps then stop; insufficient cycles, oblique view. |

Other rejects include standing (#140), lying/rolling (#182), snow/ball/toy play (#82, #92, #122, #180), and brief movement followed by stopping/sitting (#78, #86, #106). The full CSV records every reason. #106 is variable frame rate: nominal 60 fps but average about 44.91 fps; timestamps, rather than index/average-fps arithmetic, should govern any future temporal measurements. Dense decoded-timestamp sheets are supplied for #115 and #198.

The two leads are visually unlike the existing Dalmatian and brown dog02 example. Their supplied dog UUIDs are distinct from each other. Existing PetLens examples have no DogReID UUID mapping; visual difference and source provenance support novelty but cannot provide a universal cross-dataset identity guarantee. The JSON/CSV retain both UUIDs and the exact archive member for definitive review.

## Identity-safe handling

[identity-registry.csv](identity-registry.csv) records all 1,553 original dog IDs and a canonical namespaced `identity_group_key = dogreid1553:<casefolded DOG_ID>`. Original UUID spelling is retained because an ID in the archive contains uppercase characters. Every clip, crop, trimmed segment and augmentation must inherit its dog key. Deduplicate canonical keys before assigning partitions.

All PetLens splits are deliberately **unassigned** and all retrieved clips have `training_approved=false`. Before training, assign train/validation/test once per dog group and propagate that assignment to every video of the dog. `build_review.validate_identity_splits` raises if assigned rows for the same dog use different partitions. Run it over the complete import manifest, including earlier imports; validation of this review alone cannot police unrelated pipelines.

Both original `SPLIT_CLOSED_SET` and `SPLIT_OPEN_SET`, plus scene `GROUP`, are retained separately. They are different benchmark protocols and must not be mixed into one split rule. Scene-disjoint query/gallery grouping does not replace dog-disjoint PetLens training/test assignment. No pet name, breed or video UUID should substitute for dog UUID when splitting.

All original CSV MD5 checksums matched the Dataverse records. All 17 local MP4 sizes and CRC32 values match the ZIP directory; SHA256 hashes are in the manifest. Whole-archive MD5 verification was intentionally impossible without the prohibited full download.

## Reproduce or extend the screen

From the repository root:

```bash
# Network: small metadata files and ZIP directories only
python reports/dogreid-1553/screen.py index

# Network: initial extreme-wide bbox sample (on a fresh output directory)
python reports/dogreid-1553/screen.py previews wide

# Network: append 100 new dogs near bbox aspect ratio 1.65
python reports/dogreid-1553/screen.py previews

# Network: extract just selected members, preferably in short batches
python reports/dogreid-1553/screen.py fetch 115 198

# Local: verify clip integrity and regenerate manifests and comparison
python reports/dogreid-1553/build_review.py
```

The existing preview manifest freezes numbering and UUID associations; `previews` appends a new batch, so do not rerun it expecting identical numbering. Bbox ratio only prioritizes visual inspection; it is not a walking classifier. The source metadata and ZIP indexes should be kept together; if a future version changes the archive IDs/sizes, refresh the metadata before accessing it.

The smallest next step is to review these two leads and selectively inspect alternate clips for their dog IDs, then expand the first-frame sample if neither is acceptable. A few hundred more crops cost tens of MB, and selected MP4s cost their member sizes. For a reliable supply of five strict examples, request a small author-curated CC0 bundle of lateral walks (roughly 5–10 seconds each, several visible hind-paw cycles, stable low camera), with dog/video UUIDs and original timestamps. No author was contacted. If range support stops working, halt; request individual clips or a small subset archive rather than falling back to Videos.zip. The 1.52 GB image archive is a preview-only fallback and cannot establish gait.
