"""Verify the existing Husky package and export isolated blind human annotations.

No models, inference, training, or prediction files are used. Original package
files are read-only; preparation creates a new manifest with exclusive creation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import uuid
import zipfile

from training import prepare_paw_annotations as p

GROUP = 'husky-evaluation'
PACKAGE = Path('tmp/petlens-husky-evaluation/PetLens_Husky_Evaluation')
DEFAULT_MANIFEST = Path('reports/husky-evaluation/annotation-manifest-v1.json')
EXPORTS = Path('reports/husky-evaluation/annotations')
TYPE = 'blind-hind-paw-evaluation'


def source(root, path):
    resolved = (root / path).resolve()
    p.require(resolved.is_relative_to(root.resolve()), 'Source escapes repository')
    return resolved


def record(root, path):
    return dict(path=str(path.relative_to(root)), sha256=p.digest(path))


def inspect_package(root=p.ROOT, package=PACKAGE, encode=False):
    """Sequential decoding establishes indices; container frame count is advisory."""
    import cv2
    import numpy as np

    root = root.resolve()
    directory = source(root, package)
    preparation = p.load_json(directory / 'PREPARATION_MANIFEST.json')
    samples = p.load_json(directory / 'FRAME_INDEX.json')
    video = source(root, directory / preparation['prepared_file'])
    p.require(p.digest(video) == preparation['prepared_sha256'], 'Prepared video hash mismatch')
    p.require(len(samples) == 20, 'Expected exactly 20 sampled PNGs')
    indices = [s['frame_index_zero_based'] for s in samples]
    p.require(all(type(i) is int and i >= 0 for i in indices) and
              indices == sorted(set(indices)), 'Invalid/duplicate sampled frame index')
    p.require(indices == preparation['annotated_frame_indices_zero_based'], 'Sample index manifest mismatch')
    by_index = dict(zip(indices, samples))
    cap = cv2.VideoCapture(str(video))
    frames, encoded = [], {}
    try:
        p.require(cap.isOpened(), 'Cannot decode Husky video')
        container_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        while True:
            ok, image = cap.read()
            if not ok:
                break
            index = len(frames)
            height, width = image.shape[:2]
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            p.require([width, height] == preparation['prepared_video_size_px'], 'Prepared dimensions mismatch')
            p.require(p.finite(t) and t >= 0 and (not frames or t > frames[-1]['timestampSeconds']),
                      'Invalid/nonmonotonic decoded timestamp')
            frame = dict(frameIndex=index, timestampSeconds=t,
                         pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
            if index in by_index:
                sample = by_index[index]
                png = source(root, directory / sample['file'])
                p.require(png.is_relative_to(directory), 'Sample escapes package')
                saved = cv2.imread(str(png))
                p.require(saved is not None and np.array_equal(saved, image),
                          f'Sampled PNG/source-frame pixel mismatch: {index}')
                p.require(sample['annotation_status'] == 'not_reviewed' and
                          abs(t - sample['source_time_seconds_approx']) <= 0.001,
                          f'Sample timestamp/status mismatch: {index}')
                frame['sample'] = record(root, png)
            if encode:
                ok, buffer = cv2.imencode('.png', image)
                p.require(ok, 'Cannot encode original context frame')
                # Serve exact existing PNG bytes on sampled frames, original decoded pixels otherwise.
                encoded[index] = png.read_bytes() if 'sample' in frame else buffer.tobytes()
            frames.append(frame)
    finally:
        cap.release()
    p.require(len(frames) == preparation['full_prepared_frame_count'] == 63 and
              all(i < len(frames) for i in indices), 'Actual decoded frame count mismatch')
    # Source recording is absent. Do not invent a per-frame original-source mapping.
    interval = re.search(r'frames (\d+) through (\d+) inclusive', preparation['method'])
    p.require(interval is not None, 'Missing source-frame-range statement')
    start, stop = map(int, interval.groups())
    manifest = dict(
        schemaVersion=1, annotationType=TYPE, group=GROUP,
        datasetId='petlens-husky-evaluation-' + preparation['prepared_sha256'][:16],
        split='exploratory_evaluation', modelSelectionAllowed=False, blind=True,
        video=record(root, video), preparation=record(root, directory / 'PREPARATION_MANIFEST.json'),
        frameIndexSource=record(root, directory / 'FRAME_INDEX.json'),
        originalSource=dict(file=preparation['source_file'], sha256=preparation['source_sha256'],
                            verification='Claim from preparation manifest; original recording unavailable'),
        frameWidth=width, frameHeight=height, frameCount=len(frames), fps=fps,
        selectedFrames=indices, frames=frames,
        frameCountDiscrepancy=dict(
            declaredSourceFrameRangeInclusive=[start, stop], impliedSourceFrameCount=stop - start + 1,
            containerReportedFrameCount=container_count, preparationDeclaredFrameCount=63,
            decodedPreparedFrameCount=len(frames),
            resolution='Use sequentially decoded prepared-video indices 0-62. Source range and container imply 64; only 63 decode. The absent source correspondence is unresolved; no source-frame offset or gap is fabricated.'),
        timestampPolicy='Decoded prepared-video timestamps, relative to first retained frame; screen-recording sampling is variable, not native gait timing',
        annotationPolicy='Sampled frames only. Human physical A/B paw-tip points; visible coordinates can retain uncertain anatomy. No forced left/right mapping. Context frames are read-only.',
        limitations=preparation['limitations'], opencvVersion=cv2.__version__)
    return manifest, encoded


def prepare(output, root=p.ROOT, package=PACKAGE):
    p.require(not output.exists(), f'Manifest exists; choose a fresh path: {output}')
    manifest, _ = inspect_package(root, package)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return manifest


def session(manifest_path, root=p.ROOT):
    """Reverify source hashes/pixels on startup; keep verified frame bytes in memory."""
    stored = p.load_json(manifest_path)
    for name in ('video', 'preparation', 'frameIndexSource'):
        p.checked(root, stored[name])
    package = Path(stored['preparation']['path']).parent
    actual, encoded = inspect_package(root, package, encode=True)
    p.require(actual == stored, 'Stale Husky manifest; source verification differs')
    blank = dict(status='unmarked', x=None, y=None)
    records = [dict(datasetId=stored['datasetId'], group=GROUP, split=stored['split'],
                    frameIndex=f['frameIndex'], timestampSeconds=f['timestampSeconds'],
                    width=stored['frameWidth'], height=stored['frameHeight'],
                    imageSha256=f['sample']['sha256'],
                    human=dict(A=copy.deepcopy(blank), B=copy.deepcopy(blank), modelExposed=False),
                    labelHashes={paw: p.label_digest(blank) for paw in p.PAWS})
               for f in stored['frames'] if 'sample' in f]
    base = dict(schemaVersion=1, annotationType=TYPE, blind=True,
                referenceSha256=p.digest(manifest_path),
                sourceConfiguration=stored, records=records)
    return base, encoded


def initial_draft(base):
    draft = {k: copy.deepcopy(base[k]) for k in
             ('schemaVersion', 'annotationType', 'referenceSha256', 'sourceConfiguration', 'blind')}
    draft['reviewer'] = ''
    draft['reviews'] = [dict(datasetId=r['datasetId'], frameIndex=r['frameIndex'], physicalPaw=paw,
        originalLabelSha256=p.label_digest(r['human'][paw]), imageSha256=r['imageSha256'],
        correctedLabel=copy.deepcopy(r['human'][paw]), identityState='unreviewed', anatomicalKeypoint=None,
        landmarkConfirmed=False, continuityConfirmed=False, modelExposed=False, reviewer='', evidence='')
        for r in base['records'] for paw in p.PAWS]
    return draft


def validate(base, draft, require_reviewer=True):
    p.require(isinstance(draft, dict), 'Expected a blind evaluation draft object')
    for name in ('schemaVersion', 'annotationType', 'referenceSha256', 'sourceConfiguration', 'blind'):
        p.require(draft.get(name) == base[name], f'Wrong blind review provenance: {name}')
    p.require(not draft.get('bulkAssignments'), 'Bulk anatomical assignments forbidden for blind Husky review')
    p.require(isinstance(draft.get('reviewer'), str) and
              (draft['reviewer'].strip() or not require_reviewer), 'Enter a reviewer ID before exporting')
    entries = draft.get('reviews')
    p.require(isinstance(entries, list), 'Missing review entries')
    original = {(r['datasetId'], r['frameIndex'], paw): r for r in base['records'] for paw in p.PAWS}
    seen, assigned = set(), {}
    counts = dict(visible=0, occluded=0, uncertain=0, ambiguous=0, unmarked=0)
    for e in entries:
        p.require(isinstance(e, dict), 'Invalid review entry')
        key = (e.get('datasetId'), e.get('frameIndex'), e.get('physicalPaw'))
        p.require(type(e.get('frameIndex')) is int and key in original and key not in seen,
                  'Unknown/duplicate evaluation review target')
        seen.add(key)
        r = original[key]
        p.require(e.get('imageSha256') == r['imageSha256'] and
                  e.get('originalLabelSha256') == p.label_digest(r['human'][key[2]]), 'Stale image/label provenance')
        p.require(e.get('modelExposed') is False, 'Blind labels cannot be model-exposed')
        label = e.get('correctedLabel')
        p.require(isinstance(label, dict) and set(label) == {'status', 'x', 'y'} and
                  label['status'] in counts, 'Invalid visibility label')
        counts[label['status']] += 1
        if label['status'] == 'visible':
            p.require(all(p.finite(label[c]) for c in ('x', 'y')) and
                      0 <= label['x'] < r['width'] and 0 <= label['y'] < r['height'], 'Invalid visible paw-tip coordinate')
        else:
            p.require(label['x'] is None and label['y'] is None, 'Nonvisible coordinates must be null')
        state, name = e.get('identityState'), e.get('anatomicalKeypoint')
        p.require(state in ('unreviewed', 'uncertain', 'verified'), 'Invalid identity state')
        p.require(all(type(e.get(k)) is bool for k in ('landmarkConfirmed', 'continuityConfirmed')) and
                  all(isinstance(e.get(k), str) for k in ('reviewer', 'evidence')), 'Invalid review fields')
        p.require('identitySource' not in e and 'bulkAssignmentId' not in e, 'No inherited anatomical mapping permitted')
        if state == 'verified':
            p.require(name in p.ANATOMICAL and label['status'] == 'visible' and
                      e['landmarkConfirmed'] and e['continuityConfirmed'] and
                      (e['reviewer'].strip() or draft['reviewer'].strip()) and e['evidence'].strip(),
                      'Anatomical assertion needs visible landmark, temporal continuity and human evidence')
            same_frame = assigned.setdefault(key[:2], set())
            p.require(name not in same_frame, 'Duplicate anatomical identity in frame')
            same_frame.add(name)
        else:
            p.require(name is None, 'Uncertain/unreviewed identity must have no anatomical channel')
    p.require(seen == set(original), 'Missing sampled review slots')
    return dict(valid=True, sampledFrames=len(base['records']), pawSlots=len(entries),
                visibilityCounts=counts, anatomicallyAsserted=sum(e['identityState'] == 'verified' for e in entries),
                incompleteReviews=[], errors=[],
                note='Evaluation only; unmarked slots remain unreviewed. Visible points with uncertain anatomy are retained without anatomical targets.')


def export_review(base, draft):
    validation = validate(base, draft)
    payloads = {'review.json': draft, 'frame-manifest.json': base['sourceConfiguration'], 'validation.json': validation}
    encoded = {name: (json.dumps(value, indent=2, allow_nan=False) + '\n').encode() for name, value in payloads.items()}
    encoded['manifest.json'] = json.dumps(dict(
        schemaVersion=1, annotationType=TYPE, split='exploratory_evaluation', modelSelectionAllowed=False,
        blind=True, createdAt=datetime.now(timezone.utc).isoformat(), referenceSha256=base['referenceSha256'],
        reviewer=draft['reviewer'], exporterSha256=p.digest(Path(__file__)),
        outputSha256={name: hashlib.sha256(value).hexdigest() for name, value in encoded.items()}), indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in encoded.items():
            archive.writestr(name, value)
    return output.getvalue()


def save_export(payload, root=p.ROOT):
    directory = root / EXPORTS
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = directory / f'husky-evaluation-human-v1-{stamp}-{uuid.uuid4().hex[:8]}.zip'
    with output.open('xb') as stream:
        stream.write(payload)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-manifest', type=Path, default=p.ROOT / DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = prepare(args.output_manifest)
    print(f'Verified {len(result["selectedFrames"])} sampled PNGs / {result["frameCount"]} decoded frames')
    print(json.dumps(result['frameCountDiscrepancy'], indent=2))
    print(f'Manifest: {args.output_manifest}')
