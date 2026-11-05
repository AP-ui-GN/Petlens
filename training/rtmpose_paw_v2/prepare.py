"""Offline schema/image audit and deterministic pilot splits. No model imports."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'reports/paw-annotation-data-v2'
IMAGES = ROOT / 'reports/paw-annotation-data-v1'
OUT = ROOT / 'reports/rtmpose-paw-v2-experiment'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    raw = (SOURCE / 'train.coco.json').read_bytes()
    data = json.loads(raw)
    schema = json.loads((ROOT / 'training/canine_keypoint_schema.json').read_text())
    expected = [k['id'] for k in schema['keypoints']]
    assert len(expected) == 17
    assert len(data['categories']) == 1
    assert data['categories'][0]['keypoints'] == expected
    assert data['categories'][0]['id'] == 1
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name, sha in manifest['outputSha256'].items():
        assert digest((SOURCE / name).read_bytes()) == sha, name
    with zipfile.ZipFile(SOURCE / 'dalmatian-reviewed.zip') as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert archive.read(name) == (SOURCE / name).read_bytes(), name
    images = {i['id']: i for i in data['images']}
    assert len(images) == len(data['images']) == 46
    assert len({a['id'] for a in data['annotations']}) == 42
    assert len({a['image_id'] for a in data['annotations']}) == 42
    image_hashes = {}
    for image in images.values():
        path = (IMAGES / image['file_name']).resolve()
        assert path.is_relative_to(IMAGES.resolve())
        payload = path.read_bytes()
        assert payload[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', payload[16:24]) == (image['width'], image['height'])
        image_hashes[image['id']] = digest(payload)
    counts = Counter()
    for ann in data['annotations']:
        image = images[ann['image_id']]
        w, h = image['width'], image['height']
        assert ann['category_id'] == 1 and ann['iscrowd'] == 0
        assert len(ann['keypoints']) == 51
        assert ann['bbox'] == [0, 0, w, h] and ann['area'] == w * h
        assert ann['bbox_source'] == 'full_image_extent_not_an_annotated_dog_box'
        visible = {}
        for k, name in enumerate(expected):
            x, y, v = ann['keypoints'][3*k:3*k+3]
            assert all(math.isfinite(t) for t in (x, y, v))
            if v:
                assert k in (13, 16) and v == 2 and 0 <= x < w and 0 <= y < h
                counts[name] += 1
                visible[name] = (x, y)
            else:
                assert (x, y, v) == (0, 0, 0)
        assert ann['num_keypoints'] == len(visible) == len(ann['anatomical_reviews'])
        for review in ann['anatomical_reviews']:
            assert review['imageSha256'] == image_hashes[image['id']]
            assert review['frameIndex'] == image['frame_id']
            assert review['datasetId'] == image['video_id']
            assert review['identityState'] == 'verified'
            assert review['landmarkConfirmed'] and review['continuityConfirmed']
            label = review['correctedLabel']
            assert visible.pop(review['anatomicalKeypoint']) == (label['x'], label['y'])
            assert {'A': 'right_back_paw', 'B': 'left_back_paw'}[review['physicalPaw']] == review['anatomicalKeypoint']
        assert not visible
    assert counts == {'left_back_paw': 39, 'right_back_paw': 40}
    # Reuse only the selected single-dog detection from the exact annotated run.
    # Never inspect predicted keypoints to choose/expand a box or supply labels.
    sequence = manifest['sourceConfiguration']['sequences'][0]
    detection_path = ROOT / sequence['predictions']['path']
    detection_raw = detection_path.read_bytes()
    detection_sha = digest(detection_raw)
    assert detection_sha == sequence['predictions']['sha256']
    detections = json.loads(detection_raw)
    assert detections['videoSha256'] == sequence['video']['sha256']
    frames = {f['frameIndex']: f for f in detections['frames']}
    boxed, exclusions, box_evidence = [], [], []
    for ann in data['annotations']:
        image = images[ann['image_id']]
        frame = frames[image['frame_id']]
        if not frame['detectionSuccess'] or frame['dogCandidateCount'] != 1 or 'boundingBoxXyxy' not in frame:
            exclusions.append(dict(frame_id=image['frame_id'], targets=ann['num_keypoints'],
                                   reason=frame.get('failureReason', 'no unambiguous selected dog box')))
            continue
        x1, y1, x2, y2 = frame['boundingBoxXyxy']
        assert all(math.isfinite(v) for v in (x1, y1, x2, y2))
        assert 0 <= x1 < x2 <= image['width'] and 0 <= y1 < y2 <= image['height']
        for k in (13, 16):
            x, y, v = ann['keypoints'][3*k:3*k+3]
            assert not v or (x1 <= x <= x2 and y1 <= y <= y2), ('reviewed paw outside saved box', image['frame_id'])
        bbox = [x1, y1, x2-x1, y2-y1]
        boxed.append(dict(ann, bbox=bbox, area=bbox[2]*bbox[3],
                          bbox_source='saved_single_dog_rtdetr_detection',
                          detection_confidence=frame['detectionConfidence']))
        box_evidence.append(dict(frame_id=image['frame_id'], bbox_xyxy=[x1, y1, x2, y2],
                                 confidence=frame['detectionConfidence'],
                                 image_sha256=image_hashes[image['id']]))
    OUT.mkdir(exist_ok=True)
    summaries = {}
    for name, choose in {
        'pilot-train': lambda f: 46 <= f <= 65,
        'buffer-excluded': lambda f: 66 <= f <= 75,
        'temporal-diagnostic': lambda f: 76 <= f <= 90,
        'all-reviewed': lambda f: True,
    }.items():
        anns = [a for a in boxed if choose(images[a['image_id']]['frame_id'])]
        ids = {a['image_id'] for a in anns}
        # Keep audit evidence in the hashed source; derived COCO needs no repeated
        # multi-kilobyte conversation records.
        subset = dict(data, images=[i for i in data['images'] if i['id'] in ids],
                      annotations=[{k: v for k, v in a.items() if k != 'anatomical_reviews'} for a in anns])
        subset['info'] = dict(data['info'], split=name, model_selection_allowed=False,
                              validation_scope='same-video diagnostic only',
                              bbox_source_sha256=detection_sha,
                              excluded_frames_without_unambiguous_box=exclusions)
        payload = json.dumps(subset, indent=2) + '\n'
        (OUT / (name + '.coco.json')).write_text(payload)
        summaries[name] = dict(frames=len(ids), targets=sum(a['num_keypoints'] for a in anns),
                               frame_ids=[i['frame_id'] for i in subset['images']],
                               sha256=digest(payload.encode()))
    audit = dict(source_sha256=digest(raw), zip_sha256=digest((SOURCE / 'dalmatian-reviewed.zip').read_bytes()),
                 image_root=str(IMAGES.relative_to(ROOT)), image_count=46, annotated_frames=42,
                 image_dimensions=[1080, 1920], image_sha256={images[k]['file_name']: v for k, v in image_hashes.items()},
                 keypoint_order=expected, targets=dict(counts), visibility='79 visible v=2; every other slot unknown v=0',
                 splits=summaries, unique_videos=len({i['video_id'] for i in images.values()}),
                 bbox='saved single-dog RT-DETR boxes; no interpolation/expansion from paw labels',
                 box_source=str(detection_path.relative_to(ROOT)), box_source_sha256=detection_sha,
                 box_evidence=box_evidence, box_exclusions=exclusions,
                 checks='schema, bounds, PNG dimensions, review coordinates, image and payload SHA256, ZIP parity, video-bound detection hashes, box bounds and paw coverage')
    (OUT / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(dict(targets=dict(counts), splits=summaries), indent=2))


if __name__ == '__main__':
    main()
