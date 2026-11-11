# Video selection: no suitable clip selected

Both original files were downloaded individually and their SHA-1 values matched
the checksums published on their Commons file pages. FFprobe frame timestamps
were checked against sequential OpenCV decoding. No models or dependencies were
downloaded, no training occurred, and no contact labels were generated.

| Candidate | Decoded video | Decision |
| --- | --- | --- |
| [Nora: Dog walking in the Mission in San Francisco](https://commons.wikimedia.org/wiki/File:Dog_walking_in_the_Mission_in_San_Francisco.ogv) | 1280×720, 24 FPS, 404 frames, about 16.83 s of video | REJECTED |
| [Pro dog walker — Tokyo — 2024 Nov 1](https://commons.wikimedia.org/wiki/File:Pro_dog_walker_-_Tokyo_-_2024_Nov_1.webm) | 1920×1080, 30 FPS, 271 frames, about 9.03 s of video | REJECTED |

## Nora

Regular PTS from 0 to 16.791667 seconds, time base 1/24, exactly one frame every
41.667 ms. Overall audio/video container duration is 16.873651 seconds. This
establishes the available file's timing, not native camera sampling or an
unedited camera original. The page credits Sage Ross (Ragesoss), dates the work
27 September 2011, and places it in LiAnna Davis's dog Nora category. This is
a distinct source and dog appearance from the affected laboratory dog in S004.

The camera follows Nora from approach through a side passage into a rear view.
The best close side passage was examined using consecutive original frames
132–155 (5.500–6.458 s), as well as the full-clip overview and full-resolution
source frames. Airborne paw poses can be seen, but motion blur, shaggy dark paw
boundaries and repeated near/far limb overlap make contact boundaries and paw
identity unreliable across the requested continuous span. There is no certified
8–12-second interval supporting a continuously tracked front/hind pair with
repeatable contact evidence. This does not mean no walking or cycles are visible;
it means no contact-verified cycle count is asserted. Do not fill uncertainty
from apparent foot proximity or from these screening notes.

License: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
Retain credit to Sage Ross, title, source and license links, notices, changes
and no-endorsement wording. Shared adaptations of the media must use the same
or a permitted compatible license. These terms do not make paw evidence clear.
Model-weight ShareAlike obligations were not determined in this rejected-clip
screen; no commercial training approval is asserted.

Evidence: `tmp/canine-candidate-nora-20261111/original.ogv`, `ffprobe.json`,
`overview.jpg`, `consecutive.jpg`, and original-resolution consecutive frames.
Inspection images are adaptations under CC BY-SA 3.0; the original is unchanged.

## One alternative

Tokyo was checked as one small individually downloadable walking video. The
current Commons source file is itself a crop/transcode of an older upload;
camera-native frame rate is not established. Its PTS run from 0.003 to 9.003 s,
with 33/34 ms increments on a 1/1000 time base. Container duration is 9.058 s.

The camera looks from behind at a dense group of small dogs. Front paws are
hidden by bodies, nearby dogs and the rear viewpoint; visible feet are too small
and overlapping for repeatable paw-ground contact judgments. No single dog has
an assessable front/hind pair over the requested span. Good encoded FPS does
not compensate for this view. No training candidate or review manifest was made.

Credit: Nesnad, 1 November 2024;
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Preserve title,
source, attribution, license link, changes and no endorsement; shared adapted
media require the same or a permitted compatible license. The file page also
flags personality rights for depicted people. This was not the reason for
rejection: the paw evidence alone is insufficient.

Evidence: `tmp/canine-candidate-tokyo-20261111/original.webm`, `ffprobe.json`,
`overview.jpg`, and sampled original-resolution frames. Inspection images are
adaptations under CC BY-SA 4.0; the original is unchanged.

## Stop condition and next action

Zero accepted spans; no footage has been forced into training. The 17 previously
screened DogReID videos were not re-evaluated or downloaded. Existing first-frame
preview sheets/records were consulted as leads, and the existing contact-sheet
utility was reused. No Dataverse archive was downloaded. No third candidate was
inspected. Existing code, S004 work and unrelated files were left unchanged.

**One next action:** supply one owner-recorded 8–12-second side-on walking clip
of a clearly different dog on a hard contrasting surface, at 30–60 FPS with
explicit labeling/model-development permission. After it passes the same visual
check, use the existing gait-event reviewer to label a contiguous front/hind
span. Do not begin labeling either rejected clip.

Exact hashes, original download links, timing and rejection records are in
`selection.json`.
