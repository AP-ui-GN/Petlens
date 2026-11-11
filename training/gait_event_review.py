"""Blind human gait-event references using the existing annotation canvas.

No predictions, prior annotations, event estimation, or model imports are used.
Only human-entered records can become review assertions; exports are not an
adjudicated reference until a separate independent review has been reconciled.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, urlsplit
import uuid
import zipfile

from training import prepare_paw_annotations as p

TYPE = 'blind-gait-event-review'
DIRECTORY = Path('reports/gait-event-review-v1')
MANIFEST = DIRECTORY / 'frame-manifest.json'
UI = Path('tmp/rtmpose-test/paw-tracking-experiment/manual-annotation')
SOURCES = {
    'gait-dalmatian': ('tests/13792872-hd_1080_1920_30fps (1).mp4', 46, 74),
    'gait-dog02': ('test/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s003.ogv', 0, 59),
    'gait-s004': ('tests/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv', 0, 59),
}
PAWS = ('A', 'B')
STATES = ('unreviewed', 'airborne', 'contacting', 'unknown', 'occluded', 'uncertain', 'unassessable')
CONTINUITY = ('unreviewed', 'start', 'continuous', 'broken', 'uncertain', 'unassessable')
BOUNDARIES = (
    ('initialContactLastAirborne', 'airborne'),
    ('initialContactFirstContacting', 'contacting'),
    ('liftOffLastContacting', 'contacting'),
    ('liftOffFirstAirborne', 'airborne'),
    ('nextContactLastAirborne', 'airborne'),
    ('nextContactFirstContacting', 'contacting'),
)


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def inspect_sources(root=p.ROOT, groups=None):
    """Bind sequential original decoded pixels to native integer PTS, not FPS."""
    import cv2

    datasets, images = {}, {}
    for group in (('gait-dalmatian', 'gait-dog02') if groups is None else groups):
        p.require(group in SOURCES, f'Unknown review source: {group}')
        relative, start, end = SOURCES[group]
        source = root / relative
        source_hash = p.digest(source)
        raw = subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams',
            '-show_frames', '-show_entries',
            'stream=time_base,width,height:frame=best_effort_timestamp',
            '-of', 'json', str(source)], text=True)
        probe = json.loads(raw)
        stream, timestamps = probe['streams'][0], probe['frames']
        numerator, denominator = map(int, stream['time_base'].split('/'))
        frames, encoded = [], {}
        cap = cv2.VideoCapture(str(source))
        try:
            p.require(cap.isOpened(), 'Cannot open original source')
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                i = len(frames)
                p.require(i < len(timestamps), 'Decoded frames exceed source PTS')
                pts = int(timestamps[i]['best_effort_timestamp'])
                t = pts * numerator / denominator
                p.require(t >= 0 and (not frames or t > frames[-1]['timestampSeconds']),
                          'Invalid native source timestamp')
                p.require(image.shape[:2] == (stream['height'], stream['width']),
                          'Original image dimensions changed')
                ok, buffer = cv2.imencode('.png', image)
                p.require(ok, 'Cannot encode original frame')
                encoded[i] = buffer.tobytes()
                frames.append(dict(frameIndex=i, originalPts=pts,
                    originalTimeBase=stream['time_base'], timestampSeconds=t,
                    pixelSha256=digest_bytes(image.tobytes()),
                    imageSha256=digest_bytes(encoded[i])))
        finally:
            cap.release()
        p.require(len(frames) == len(timestamps) and end < len(frames),
                  'Source count or review range mismatch')
        sha = p.digest(source)
        p.require(sha == source_hash, 'Source changed during frame preparation')
        datasets[group] = dict(group=group, datasetId=group + '-' + sha[:16],
            sourceVideo=dict(path=relative, sha256=sha), frameCount=len(frames),
            frameWidth=stream['width'], frameHeight=stream['height'],
            reviewStart=start, reviewEnd=end, selectedFrames=list(range(start, end + 1)),
            frames=frames, timestampPolicy='Native original-video PTS; zero-based source indices; no resampling',
            attribution=('Original Dalmatian source, retained unchanged.' if group == 'gait-dalmatian'
                         else 'Shin et al. (2013), Movie S3, DOI 10.1371/journal.pone.0059875; original embedded CC BY 3.0 attribution retained.'))
        if group == 'gait-s004':
            datasets[group].update(
                physicalPaws=['A', 'B', 'C', 'D'],
                pawRoles={'A': 'Hind physical A', 'B': 'Hind physical B',
                          'C': 'Front physical C', 'D': 'Front physical D'},
                identityPolicy='Follow physical limbs, not screen order. Describe each limb. Anatomical LF/RF/LH/RH mapping remains unverified; never infer it from predictions.',
                attribution='Shin J-H et al. (2013), Movie S4, DOI 10.1371/journal.pone.0059875. Original OGV unchanged; PNG extraction for review. No endorsement implied.',
                rights=dict(status='attribution_required',
                    source='https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0059875',
                    fileDescription='https://commons.wikimedia.org/wiki/File:Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv',
                    embeddedLicense='https://creativecommons.org/licenses/by/3.0/',
                    commonsLicense='https://creativecommons.org/licenses/by/2.5/',
                    evidence='Publication grants attributed reuse; embedded CC BY 3.0 and Commons CC BY 2.5 discrepancy retained. Commercial reuse permitted with attribution; source notices preserved.'),
                identityGroup='shin-2013-s003-s004-unresolved', dogIdentityVerified=False,
                trainingApproved=False,
                timingLimit='Original available OGV PTS, 12 FPS (83.33 ms). Sensor capture rate is not independently attested; no subframe timing claims.',
                reviewDirectory='reports/canine-contact-batch-v1/reviews')
        images[group] = encoded
    return dict(schemaVersion=1, annotationType=TYPE, datasets=datasets), images


def prepare(path=MANIFEST, root=p.ROOT, groups=None):
    manifest, _ = inspect_sources(root, groups=groups)
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as handle:
        json.dump(manifest, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return manifest


def session(path=MANIFEST, root=p.ROOT, group=None):
    stored = p.load_json(root / path)
    expected = stored
    if group is not None:
        p.require(group in SOURCES and group in stored.get('datasets', {}),
                  f'{group}: unknown or missing dataset in saved manifest; review not opened')
        expected = dict(stored, datasets={group: stored['datasets'][group]})
    try:
        actual, images = (inspect_sources(root) if group is None
                          else inspect_sources(root, groups=(group,)))
        p.require(actual == expected, 'Original source/frame manifest changed; review not opened')
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise p.ValidationError(f'{group or "All datasets"}: provenance validation failed: {exc}') from exc
    # Keep the full saved-manifest hash: existing drafts retain their provenance.
    return expected, images, p.digest(root / path)


def initial_draft(meta, manifest_hash):
    paws = meta.get('physicalPaws', PAWS)
    return dict(schemaVersion=1, annotationType=TYPE, blind=True,
        manifestSha256=manifest_hash, datasetId=meta['datasetId'],
        reviewer='', independenceDeclaration='unreviewed', modelExposed=False,
        previousLabelsExposed=False, pawDescriptions={paw: '' for paw in paws},
        observations={str(i): {paw: dict(visibility='unreviewed',
            continuity='unreviewed', supportState='unreviewed', notes='') for paw in paws}
            for i in meta['selectedFrames']}, strides=[])


def validate(meta, manifest_hash, draft):
    paws = meta.get('physicalPaws', PAWS)
    p.require(isinstance(draft, dict) and draft.get('schemaVersion') == 1 and
              draft.get('annotationType') == TYPE and draft.get('blind') is True and
              draft.get('manifestSha256') == manifest_hash and
              draft.get('datasetId') == meta['datasetId'], 'Wrong review provenance')
    p.require(set(draft) == set(initial_draft(meta, manifest_hash)), 'Unknown review fields')
    p.require(draft.get('modelExposed') is False and draft.get('previousLabelsExposed') is False,
              'Exposed labels cannot enter the blind workflow')
    p.require(isinstance(draft.get('reviewer'), str), 'Invalid reviewer')
    p.require(draft.get('independenceDeclaration') in
              ('unreviewed', 'no_prior_exposure', 'prior_exposure'), 'Invalid independence declaration')
    p.require(isinstance(draft.get('pawDescriptions'), dict) and
              set(draft['pawDescriptions']) == set(paws) and
              all(isinstance(v, str) for v in draft['pawDescriptions'].values()), 'Invalid physical paw descriptions')
    observations = draft.get('observations')
    p.require(isinstance(observations, dict) and
              set(observations) == {str(i) for i in meta['selectedFrames']}, 'Missing or foreign review frames')
    for frame_paws in observations.values():
        p.require(isinstance(frame_paws, dict) and set(frame_paws) == set(paws), 'Invalid physical paws')
        for observation in frame_paws.values():
            p.require(isinstance(observation, dict) and
                set(observation) == {'visibility', 'continuity', 'supportState', 'notes'} and
                observation.get('visibility') in ('unreviewed', 'visible', 'occluded', 'uncertain', 'unassessable') and
                observation.get('continuity') in CONTINUITY and
                observation.get('supportState') in STATES and
                isinstance(observation.get('notes'), str), 'Invalid observation')
            if observation['supportState'] in ('airborne', 'contacting'):
                p.require(observation['visibility'] == 'visible', 'Definite support state requires visible paw')
        if meta.get('physicalPaws'):
            for paw, observation in frame_paws.items():
                if observation['supportState'] in ('airborne', 'contacting'):
                    p.require(observation['continuity'] in ('start', 'continuous') and
                              draft['pawDescriptions'][paw].strip(),
                              'Definite support requires described, reliable physical identity')
    strides = draft.get('strides')
    p.require(isinstance(strides, list), 'Invalid stride list')
    ids, complete = set(), 0
    for stride in strides:
        p.require(isinstance(stride, dict) and isinstance(stride.get('id'), str) and
                  bool(stride['id']) and stride['id'] not in ids, 'Invalid or duplicate stride ID')
        ids.add(stride['id'])
        p.require(set(stride) == {'id', 'physicalPaw', 'status', 'boundaries', 'notes'} and
                  stride.get('physicalPaw') in paws and stride.get('status') in
                  ('unreviewed', 'complete', 'occluded', 'uncertain', 'unassessable') and
                  isinstance(stride.get('notes'), str), 'Invalid stride assertion')
        boundaries = stride.get('boundaries')
        p.require(isinstance(boundaries, dict) and set(boundaries) == {k for k, _ in BOUNDARIES},
                  'Invalid event bracket fields')
        for boundary in boundaries.values():
            if boundary is None:
                continue
            p.require(isinstance(boundary, dict) and set(boundary) == {'frameIndex', 'timestampSeconds'} and
                      type(boundary.get('frameIndex')) is int and
                      boundary['frameIndex'] in meta['selectedFrames'], 'Event outside review window')
            i = boundary['frameIndex']
            p.require(type(boundary.get('timestampSeconds')) in (int, float) and
                      boundary['timestampSeconds'] == meta['frames'][i]['timestampSeconds'],
                      'Event timestamp differs from native source')
    for stride in strides:
        boundaries = stride['boundaries']
        if stride['status'] != 'complete':
            continue
        p.require(all(boundaries.values()), 'Complete stride requires all six bracket boundaries')
        indices = [boundaries[k]['frameIndex'] for k, _ in BOUNDARIES]
        a, b, c, d, e, f = indices
        p.require(a < b <= c < d <= e < f, 'Contact/lift-off/next-contact brackets are out of order')
        paw = stride['physicalPaw']
        p.require(draft['pawDescriptions'][paw].strip() and stride['notes'].strip(),
                  'Complete stride needs physical-paw description and human evidence')
        for i in range(a, f + 1):
            observation = observations[str(i)][paw]
            p.require(observation['visibility'] == 'visible' and
                      (observation['continuity'] == 'continuous' or
                       (i == a and observation['continuity'] == 'start')),
                      f'Complete stride has missing/uncertain physical continuity at frame {i}')
        for key, state in BOUNDARIES:
            p.require(observations[str(boundaries[key]['frameIndex'])][paw]['supportState'] == state,
                      'Event boundary lacks the corresponding definite human support observation')
        for first, last, state in ((b, c, 'contacting'), (d, e, 'airborne')):
            p.require(all(observations[str(i)][paw]['supportState'] == state
                          for i in range(first, last + 1)),
                      'Complete stride needs reviewed support states throughout stance and swing')
        # Duplicate/overlapping intervals of one paw cannot inflate the stride count.
        for other in strides:
            if other is stride or other.get('status') != 'complete' or other.get('physicalPaw') != paw:
                continue
            ob = other.get('boundaries', {})
            start, end = ob.get('initialContactFirstContacting'), ob.get('nextContactFirstContacting')
            if isinstance(start, dict) and isinstance(end, dict):
                p.require(not (b < end.get('frameIndex', -1) and start.get('frameIndex', -1) < f),
                          'Overlapping complete assertions for the same physical paw')
        complete += 1
    return dict(valid=True, humanAssertedCompleteStrides=complete, adjudicated=False,
        independenceDeclared=draft['independenceDeclaration'] == 'no_prior_exposure',
        unreviewedPawFrames=sum(o['visibility'] == 'unreviewed'
            for paws in observations.values() for o in paws.values()),
        note='Human assertions only. Partial and uncertain reviews are retained. Two independent reviews and adjudication are still required.')


def export_review(meta, manifest_hash, draft):
    report = validate(meta, manifest_hash, draft)
    p.require(draft['reviewer'].strip() and draft['independenceDeclaration'] != 'unreviewed',
              'Reviewer ID and independence declaration required for export')
    payloads = {'review.json': draft, 'frame-manifest.json': meta, 'validation.json': report}
    encoded = {name: (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
               for name, value in payloads.items()}
    encoded['manifest.json'] = json.dumps(dict(schemaVersion=1, annotationType=TYPE,
        createdAt=datetime.now(timezone.utc).isoformat(), manifestSha256=manifest_hash,
        sourceVideo=meta['sourceVideo'], reviewer=draft['reviewer'],
        exporterSha256=p.digest(Path(__file__)), adjudicated=False,
        outputSha256={name: digest_bytes(value) for name, value in encoded.items()}), indent=2).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in encoded.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def save_export(payload, root=p.ROOT, directory=None):
    folder = root / (directory or DIRECTORY / 'reviews')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('review-' + uuid.uuid4().hex + '.zip')
    with target.open('xb') as handle:
        handle.write(payload)
    return target


def compare_exports(first, second, paw_map):
    """Flag differences only, after a human supplies physical-paw correspondence."""
    reviews = []
    for path in (first, second):
        with zipfile.ZipFile(path) as archive:
            provenance = json.loads(archive.read('manifest.json'))
            for name, sha in provenance['outputSha256'].items():
                p.require(digest_bytes(archive.read(name)) == sha, 'Review export hash mismatch')
            meta = json.loads(archive.read('frame-manifest.json'))
            draft = json.loads(archive.read('review.json'))
            validate(meta, provenance['manifestSha256'], draft)
            p.require(draft['reviewer'].strip() and
                      draft['independenceDeclaration'] == 'no_prior_exposure',
                      'Comparison requires independent reviewer declarations')
            reviews.append((meta, draft, provenance))
    (meta, left, lp), (other, right, rp) = reviews
    p.require(meta == other and lp['manifestSha256'] == rp['manifestSha256'],
              'Reviews have different source provenance')
    p.require(left['reviewer'] != right['reviewer'], 'Two different reviewer IDs required')
    paws = set(left['pawDescriptions'])
    p.require(set(paw_map) == paws and set(paw_map.values()) == paws,
              'Supply a one-to-one human-confirmed physical-paw correspondence')
    p.require(all(d.strip() for draft in (left, right) for d in draft['pawDescriptions'].values()),
              'Describe every physical paw before comparison')
    disagreements, incomplete = [], []
    for i in meta['selectedFrames']:
        for paw, other_paw in paw_map.items():
            a, b = left['observations'][str(i)][paw], right['observations'][str(i)][other_paw]
            record = dict(frameIndex=i, timestampSeconds=meta['frames'][i]['timestampSeconds'],
                          physicalPaw=paw, secondPhysicalPaw=other_paw)
            fields = [field for field in ('visibility', 'continuity', 'supportState') if a[field] != b[field]]
            if fields:
                disagreements.append(dict(record, differingFields=fields, first=a, second=b))
            if any(o[field] == 'unreviewed' for o in (a, b)
                   for field in ('visibility', 'continuity', 'supportState')):
                incomplete.append(record)
    return dict(schemaVersion=1, adjudicated=False, trainingApproved=False,
        datasetId=meta['datasetId'], manifestSha256=lp['manifestSha256'],
        inputs=[dict(path=str(path), sha256=p.digest(Path(path))) for path in (first, second)],
        reviewers=[left['reviewer'], right['reviewer']], humanSuppliedPawCorrespondence=paw_map,
        pawDescriptions=[left['pawDescriptions'], right['pawDescriptions']],
        disagreements=disagreements, incomplete=incomplete,
        note='Differences require human resolution. Matching UNKNOWN is not a supervised target. Anatomical mapping and identity remain separate review requirements. No consensus labels generated.')


def make_handler(manifest, images, manifest_hash, root=p.ROOT):
    """Dedicated allowlist: legacy static data/API routes are never served."""
    default_group = next(iter(manifest['datasets']))

    def source_error(group):
        if group in SOURCES:
            return (f'{group}: access blocked. This dataset has not passed provenance '
                    'validation in this server. Restart with --dataset ' + group +
                    '; validation must pass before review, frames, or export are available.'), 409
        return f'{group}: unknown review source', 400

    class Handler(SimpleHTTPRequestHandler):
        def send_bytes(self, body, mime, status=200, headers=None):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            group = query.get('group', [default_group])[0]
            if url.path in ('/', '/index.html'):
                selected = query.get('dataset', [None])[0]
                if selected is None:
                    return self.send_bytes(b'', 'text/plain', 302,
                                           {'Location': '/?dataset=' + default_group})
                if selected not in manifest['datasets']:
                    message, status = source_error(selected)
                    return self.send_bytes(message.encode(), 'text/plain', status)
                html = (root / UI / 'index.html').read_text().split('<section class="card" id="adjudication">')[0]
                # Reuse the existing page and canvas; remove old links/legacy controls before paint.
                import re
                html = re.sub(r'<h1>.*?</h1><p>Dataset:.*?</p>',
                    '<h1>Blind gait-event reference review</h1><p>Source: ' +
                    ' · '.join(f'<a href="?dataset={key}">{key}</a>' for key in manifest['datasets']) +
                    '</p>', html, count=1)
                html = html.replace('</style>', 'button{white-space:normal;overflow-wrap:anywhere;max-width:100%} input{max-width:100%;box-sizing:border-box}</style>')
                html += '<script src="/gait-event-review.js"></script><script src="/annotation.js"></script></html>'
                return self.send_bytes(html.encode(), 'text/html; charset=utf-8')
            if url.path == '/annotation.js':
                js = (root / UI / 'annotation.js').read_text()
                p.require(js.count('boot().catch(error);') == 1, 'Unsupported shared viewer bootstrap')
                js = js.replace('boot().catch(error);', 'gaitEventReview.boot().catch(error);')
                return self.send_bytes(js.encode(), 'text/javascript')
            if url.path == '/gait-event-review.js':
                return self.send_bytes((root / 'training/gait-event-review.js').read_bytes(), 'text/javascript')
            if url.path.startswith('/api/predictions') or 'model-review' in url.path:
                return self.send_bytes(b'Model and prior-label access disabled in blind event review', 'text/plain', 403)
            if url.path in ('/api/session', '/api/frame'):
                if group not in manifest['datasets']:
                    message, status = source_error(group)
                    return self.send_bytes(message.encode(), 'text/plain', status)
                meta = manifest['datasets'][group]
                if url.path == '/api/session':
                    value = dict(manifestSha256=manifest_hash, source=meta,
                                 draft=initial_draft(meta, manifest_hash))
                    return self.send_bytes(json.dumps(value).encode(), 'application/json')
                try:
                    return self.send_bytes(images[group][int(query['index'][0])], 'image/png')
                except (KeyError, ValueError):
                    return self.send_bytes(b'Unknown original frame', 'text/plain', 400)
            return self.send_bytes(b'Only blind review assets are served', 'text/plain', 404)

        def do_POST(self):
            try:
                url = urlsplit(self.path)
                p.require(url.path in ('/api/validate', '/api/export'), 'Unknown endpoint')
                group = parse_qs(url.query).get('group', [''])[0]
                if group not in manifest['datasets']:
                    message, status = source_error(group)
                    return self.send_bytes(message.encode(), 'text/plain', status)
                size = int(self.headers.get('Content-Length', 0))
                p.require(0 < size < 2_000_000, 'Invalid request size')
                draft = json.loads(self.rfile.read(size))
                meta = manifest['datasets'][group]
                if url.path == '/api/validate':
                    return self.send_bytes(json.dumps(validate(meta, manifest_hash, draft)).encode(), 'application/json')
                payload = export_review(meta, manifest_hash, draft)
                output = save_export(payload, root, meta.get('reviewDirectory'))
                return self.send_bytes(payload, 'application/zip', headers={
                    'Content-Disposition': f'attachment; filename="{output.name}"',
                    'X-PetLens-Export-Path': str(output.relative_to(root))})
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_bytes(str(exc).encode(), 'text/plain', 400)
    return Handler


def serve(port, manifest_path=MANIFEST, group='gait-dalmatian'):
    manifest, images, sha = session(manifest_path, group=group)
    print(f'Provenance verified for {group}; other datasets are blocked in this server.', flush=True)
    print(f'Blind event review: http://localhost:{port}/?dataset={group}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), make_handler(manifest, images, sha)).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Verify original sources and write a new blank-review frame manifest')
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--dataset', choices=tuple(SOURCES),
                        help='Verify only this dataset; default: both legacy sources for prepare, Dalmatian for serve')
    parser.add_argument('--compare', type=Path, nargs=2, metavar=('FIRST_ZIP', 'SECOND_ZIP'))
    parser.add_argument('--paw-map', nargs='+', help='Human-confirmed correspondence, e.g. A:A B:B C:D D:C')
    parser.add_argument('--comparison-output', type=Path)
    args = parser.parse_args()
    if args.compare:
        p.require(args.paw_map and args.comparison_output, 'Comparison needs --paw-map and --comparison-output')
        pairs = [item.split(':') for item in args.paw_map]
        p.require(all(len(pair) == 2 for pair in pairs) and len(dict(pairs)) == len(pairs), 'Invalid paw map')
        comparison = compare_exports(*args.compare, dict(pairs))
        with args.comparison_output.open('x') as handle:
            json.dump(comparison, handle, indent=2, allow_nan=False)
            handle.write('\n')
        print(f'Flagged {len(comparison["disagreements"])} disagreements; no labels adjudicated.')
    elif args.prepare:
        prepare(args.manifest, groups=(args.dataset,) if args.dataset else None)
        print(f'Prepared original frames and native timestamps: {args.manifest}; no human labels created.')
    else:
        try:
            serve(args.port, args.manifest, args.dataset or 'gait-dalmatian')
        except p.ValidationError as exc:
            parser.exit(2, f'{exc}\n')
