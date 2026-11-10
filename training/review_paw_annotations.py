"""Serve anatomical review mode in the existing offline annotation interface."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import zipfile
from urllib.parse import parse_qs, urlsplit

from training import prepare_paw_annotations as p
from training import blind_paw_annotations as blind_review

UI = Path('tmp/rtmpose-test/paw-tracking-experiment/manual-annotation')
REFERENCE = Path('reports/paw-annotation-data-v1')


def session(root=p.ROOT):
    config = p.load_json(root / 'training/paw_annotation_sources.json')
    manifest = p.load_json(root / REFERENCE / 'manifest.json')
    p.require(manifest['sourceConfiguration'] == config, 'Stale reference configuration')
    for name in ('physical-reference.json', 'original-annotations.json'):
        p.require(p.digest(root / REFERENCE / name) == manifest['outputSha256'][name],
                  'Reference integrity mismatch')
    for spec in config['sequences']:
        for field in ('video', 'predictions', 'metadata', 'originalVideo'):
            if field in spec:
                p.checked(root, spec[field])
        for annotation in spec['annotations']:
            p.checked(root, annotation)
    records = p.load_json(root / REFERENCE / 'physical-reference.json')['records']
    return dict(schemaVersion=2, annotationType='anatomical-paw-review',
                sourceConfiguration=config,
                bulkContinuityEvidence=p.load_json(root / 'training/paw_bulk_continuity_evidence.json'),
                referenceSha256=p.digest(root / REFERENCE / 'physical-reference.json'),
                records=records)


BULK_MAPPING = {'A': 'right_back_paw', 'B': 'left_back_paw'}


def review_digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def continuity_evidence(base):
    evidence = base.get('bulkContinuityEvidence')
    if evidence is not None:
        p.require(evidence.get('schemaVersion') == 1 and
                  evidence.get('referenceSha256') == base['referenceSha256'] and
                  evidence.get('source') == 'reviewer-provided' and
                  evidence.get('independentlyVerified') is False and
                  evidence.get('frameRange') == [75, 90] and
                  evidence.get('physicalPaws') == list(p.PAWS) and
                  evidence.get('mapping') == BULK_MAPPING and
                  all(isinstance(evidence.get(k), str) and evidence[k].strip()
                      for k in ('reviewer', 'recordedOn', 'statement', 'datasetId')),
                  'Invalid reviewer continuity evidence')
    return evidence


def initial_draft(base):
    """Seed a preview without changing source annotations or browser drafts."""
    draft = {k: copy.deepcopy(base[k]) for k in
             ('schemaVersion', 'annotationType', 'referenceSha256', 'sourceConfiguration')}
    draft['reviews'] = [dict(datasetId=r['datasetId'], frameIndex=r['frameIndex'], physicalPaw=paw,
        originalLabelSha256=p.label_digest(r['human'][paw]), imageSha256=r['imageSha256'],
        correctedLabel=copy.deepcopy(r['human'][paw]), identityState='unreviewed', anatomicalKeypoint=None,
        landmarkConfirmed=False, continuityConfirmed=False, modelExposed=r['human']['modelExposed'],
        reviewer='', evidence='') for r in base['records'] for paw in p.PAWS]
    return draft


def identity_report(entries):
    """Called after validation, so duplicates and inconsistencies have failed closed."""
    return dict(duplicateAssignments=0, inconsistencies=0, missingPhysicalSlots=0,
        verifiedIdentities=sum(e['identityState'] == 'verified' for e in entries),
        missingVisibleIdentities=[dict(datasetId=e['datasetId'], frameIndex=e['frameIndex'],
                                      physicalPaw=e['physicalPaw'], identityState=e['identityState'])
                                  for e in entries if e['correctedLabel']['status'] == 'visible'
                                  and e['identityState'] != 'verified'],
        nonvisibleSlots=[dict(datasetId=e['datasetId'], frameIndex=e['frameIndex'],
                             physicalPaw=e['physicalPaw'], status=e['correctedLabel']['status'])
                         for e in entries if e['correctedLabel']['status'] != 'visible'])


def incomplete_reviews(base, draft):
    """List missing human assertions without repairing or changing any decision."""
    index = {(r['datasetId'], r['frameIndex'], paw): r['human'][paw]
             for r in base['records'] for paw in p.PAWS}
    issues = []
    entries = draft.get('reviews', []) if isinstance(draft, dict) else []
    if not isinstance(entries, list):
        return issues  # The structural validator reports this separately.
    for e in entries:
        if not isinstance(e, dict):
            continue
        key = (e.get('datasetId'), e.get('frameIndex'), e.get('physicalPaw'))
        if any(not isinstance(k, (str, int, type(None))) for k in key) or key not in index:
            continue
        verified = e.get('identityState') == 'verified'
        changed = e.get('correctedLabel') != index[key]
        missing = []
        if changed or verified:
            missing.extend(k for k in ('reviewer', 'evidence')
                           if not isinstance(e.get(k), str) or not e[k].strip())
        if verified:
            missing.extend(k for k in ('landmarkConfirmed', 'continuityConfirmed')
                           if e.get(k) is not True)
        if missing:
            issues.append(dict(datasetId=key[0], frameIndex=key[1], physicalPaw=key[2],
                               identityState=e.get('identityState'), coordinateChanged=changed,
                               missing=missing))
    return issues


def review_diagnostics(base, draft):
    """Read-only preflight for a saved draft, including all incomplete records."""
    issues = incomplete_reviews(base, draft)
    errors = []
    try:
        export_review(base, draft)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return dict(valid=not errors, errors=errors, incompleteReviews=issues,
                draftSha256=review_digest(draft),
                note='No records changed. Complete missing fields using actual human review; '
                     'bulk reviewer/evidence do not repair existing decisions.')


def bulk_preview(base, draft):
    """Conservative propagation from frame 46; never bridge a continuity gap."""
    # Run the normal validator before considering any new decisions.
    export_review(base, draft)
    evidence = continuity_evidence(base)
    slots = {(e['datasetId'], e['frameIndex'], e['physicalPaw']): e for e in draft['reviews']}
    records = {(r['frameIndex']): r for r in base['records'] if r['group'] == 'dalmatian'}
    affected, excluded, linked = [], [], True
    for frame in range(46, 91):
        r = records.get(frame)
        if not r:
            linked = False
            excluded.append(dict(frameIndex=frame, reason='Missing physical continuity record'))
            continue
        es = [slots[(r['datasetId'], frame, paw)] for paw in p.PAWS]
        continuity = r['human'].get('continuity', {})
        supplied = evidence and evidence['datasetId'] == r['datasetId'] and 75 <= frame <= 90
        # Reviewer evidence fills unreviewed continuity only; explicit breaks and
        # uncertainty remain blockers and source records are never rewritten.
        safe = all((supplied and continuity.get(paw) in (None, 'unreviewed', 'continuous')) or
                   continuity.get(paw) == 'continuous' or
                   (frame == 46 and continuity.get(paw) == 'start') for paw in p.PAWS)
        ambiguous = any(e['identityState'] == 'uncertain' or
                        e['correctedLabel']['status'] in ('uncertain', 'ambiguous') or
                        r['human'][e['physicalPaw']]['status'] in ('uncertain', 'ambiguous') for e in es)
        if not safe or ambiguous:
            linked = False
        conflict = any(e['identityState'] == 'verified' and
                       e['anatomicalKeypoint'] != BULK_MAPPING[e['physicalPaw']] for e in es)
        if conflict:
            linked = False
        if not linked:
            excluded.append(dict(frameIndex=frame, reason='Unverified/broken continuity, identity conflict or ambiguity; mapping cannot bridge this gap'))
            continue
        paws = []
        for e in es:
            paw = e['physicalPaw']
            untouched = (e['identityState'] == 'unreviewed' and e['anatomicalKeypoint'] is None
                         and e['correctedLabel'] == r['human'][paw]
                         and not any(e[k] for k in ('reviewer', 'evidence', 'landmarkConfirmed', 'continuityConfirmed')))
            neighbor_conflict = any(
                (neighbor := slots.get((r['datasetId'], frame + offset, paw))) is not None
                and neighbor['identityState'] == 'verified'
                and neighbor['anatomicalKeypoint'] != BULK_MAPPING[paw] for offset in (-1, 1))
            if untouched and e['correctedLabel']['status'] == 'visible' and not neighbor_conflict:
                paws.append(paw)
            else:
                excluded.append(dict(frameIndex=frame, physicalPaw=paw,
                                     reason=(f"Nonvisible {e['correctedLabel']['status']} label preserved"
                                             if e['correctedLabel']['status'] != 'visible' else
                                             'Adjacent identity conflict' if neighbor_conflict else
                                             'Existing human review/correction preserved')))
        if paws:
            affected.append(dict(datasetId=r['datasetId'], frameIndex=frame, physicalPaws=paws,
                                 annotationCount=len(paws),
                                 annotations=[dict(physicalPaw=paw, anatomicalKeypoint=BULK_MAPPING[paw],
                                                   label=copy.deepcopy(slots[(r['datasetId'], frame, paw)]['correctedLabel']))
                                              for paw in paws],
                                 continuitySource='reviewer-provided' if supplied else 'source-annotation'))
    return dict(mapping=BULK_MAPPING, frameRange=[46, 90], affected=affected, excluded=excluded,
                continuityEvidence=copy.deepcopy(evidence),
                frameCount=len(affected), annotationCount=sum(a['annotationCount'] for a in affected),
                previewToken=review_digest(dict(draft=draft, continuityEvidence=evidence)))


def bulk_apply(base, draft, request):
    preview = bulk_preview(base, draft)
    p.require(request.get('previewToken') == preview['previewToken'], 'Review changed; preview again')
    p.require(request.get('confirmed') is True, 'Explicit human confirmation required')
    for field in ('reviewer', 'evidence'):
        p.require(isinstance(request.get(field), str) and request[field].strip(), 'Reviewer and anatomical evidence required')
    p.require(preview['annotationCount'] > 0, 'No eligible annotations')
    result = copy.deepcopy(draft)
    operation = dict(id=review_digest(dict(token=preview['previewToken'], reviewer=request['reviewer'])),
        source='human-confirmed-mapping', confirmed=True, confirmedAt=datetime.now(timezone.utc).isoformat(),
        reviewer=request['reviewer'], evidence=request['evidence'], mapping=BULK_MAPPING,
        frameRange=[46, 90], affected=preview['affected'], excluded=preview['excluded'],
        continuityEvidence=preview['continuityEvidence'],
        beforeReviews=copy.deepcopy(draft['reviews']))
    targets = {(a['datasetId'], a['frameIndex'], paw) for a in preview['affected'] for paw in a['physicalPaws']}
    for e in result['reviews']:
        if (e['datasetId'], e['frameIndex'], e['physicalPaw']) in targets:
            e.update(identityState='verified', anatomicalKeypoint=BULK_MAPPING[e['physicalPaw']],
                     landmarkConfirmed=True, continuityConfirmed=True, reviewer=request['reviewer'],
                     evidence=request['evidence'], identitySource='human-confirmed-mapping', bulkAssignmentId=operation['id'])
    result.setdefault('bulkAssignments', []).append(operation)
    export_review(base, result)
    return result


def confirmed_mapping_export(base, draft, confirmation):
    """Use a recorded user confirmation without asking for another browser pass."""
    p.require(confirmation.get('schemaVersion') == 1 and
              confirmation.get('source') == 'reviewer-provided' and
              confirmation.get('confirmed') is True and
              confirmation.get('independentlyVerified') is False and
              confirmation.get('referenceSha256') == base['referenceSha256'] and
              confirmation.get('mapping') == BULK_MAPPING and
              confirmation.get('frameRange') == [46, 90], 'Invalid mapping confirmation')
    for field in ('reviewer', 'mappingStatement', 'coordinateReviewStatement', 'authorizationStatement'):
        p.require(isinstance(confirmation.get(field), str) and confirmation[field].strip(),
                  f'Missing reviewer-provided {field}')
    p.require(confirmation.get('continuityEvidence') == continuity_evidence(base),
              'Confirmation must retain existing continuity evidence')
    dataset = confirmation.get('datasetId')
    p.require(dataset in {r['datasetId'] for r in base['records'] if r['group'] == 'dalmatian'},
              'Wrong mapping dataset')
    preview = bulk_preview(base, draft)
    # Evidence is the user's actual statements and the existing continuity record,
    # not a fabricated anatomical observation or the physical annotator's identity.
    evidence = json.dumps(confirmation, sort_keys=True, ensure_ascii=False)
    result = bulk_apply(base, draft, dict(previewToken=preview['previewToken'], confirmed=True,
                                        reviewer=confirmation['reviewer'], evidence=evidence))
    p.require(all(old['correctedLabel'] == new['correctedLabel']
                  for old, new in zip(draft['reviews'], result['reviews'])),
              'Mapping changed existing coordinates or visibility')
    mapped = [e for e in result['reviews'] if e['datasetId'] == dataset and
              46 <= e['frameIndex'] <= 90 and e['identityState'] == 'verified' and
              e['anatomicalKeypoint'] == BULK_MAPPING[e['physicalPaw']]]
    p.require(len(mapped) == confirmation.get('expectedAnnotationCount') and
              len({e['frameIndex'] for e in mapped}) == confirmation.get('expectedFrameCount'),
              'Confirmed counts not met; existing decisions, conflicts and uncertainty preserved. No export written.')
    result['reviewerProvidedConfirmation'] = copy.deepcopy(confirmation)
    result['reviewInputScope'] = ('Supplied saved review draft' if draft.get('bulkAssignments') or
        any(e['identityState'] != 'unreviewed' or e['reviewer'] or e['evidence'] for e in draft['reviews'])
        else 'On-disk source annotations; browser-only drafts were unavailable and were not modified or merged')
    return result, export_review(base, result)


def export_review(base, draft):
    """Validate every assertion server-side; never accept browser-supplied targets."""
    p.require(isinstance(draft, dict) and draft.get('schemaVersion') == 2 and
              draft.get('annotationType') == base['annotationType'], 'Unsupported review format')
    for field in ('referenceSha256', 'sourceConfiguration'):
        p.require(draft.get(field) == base[field], 'Stale review provenance')
    operations = draft.get('bulkAssignments', [])
    p.require(isinstance(operations, list), 'Invalid bulk audit')
    operation_index = {}
    for op in operations:
        p.require(isinstance(op, dict) and op.get('source') == 'human-confirmed-mapping' and
                  op.get('confirmed') is True and op.get('mapping') == BULK_MAPPING and
                  op.get('frameRange') == [46, 90], 'Invalid bulk confirmation audit')
        p.require(all(isinstance(op.get(k), str) and op[k].strip()
                      for k in ('id', 'reviewer', 'evidence', 'confirmedAt')), 'Missing bulk audit provenance')
        before = {k: copy.deepcopy(v) for k, v in draft.items() if k not in ('bulkAssignments', 'reviews')}
        before['reviews'] = copy.deepcopy(op.get('beforeReviews'))
        p.require(isinstance(before['reviews'], list), 'Missing pre-assignment review')
        for e in before['reviews']:
            e.pop('bulkAssignmentId', None)
            e.pop('identitySource', None)
        expected = bulk_preview(base, before)
        p.require(op.get('continuityEvidence') == expected['continuityEvidence'],
                  'Bulk continuity evidence does not match reviewer provenance')
        p.require(op.get('affected') == expected['affected'] and op.get('excluded') == expected['excluded'],
                  'Bulk targets do not match safe preview')
        p.require(op['id'] not in operation_index, 'Duplicate bulk operation')
        operation_index[op['id']] = op
    entries = draft.get('reviews')
    p.require(isinstance(entries, list), 'Missing review labels')
    issues = incomplete_reviews(base, draft)
    p.require(not issues, 'Incomplete review records: ' + '; '.join(
        f"{e['datasetId']} frame {e['frameIndex']} paw {e['physicalPaw']}: missing {', '.join(e['missing'])}"
        for e in issues))
    index = {(r['datasetId'], r['frameIndex'], paw): r for r in base['records'] for paw in p.PAWS}
    seen, accepted, records = set(), {}, copy.deepcopy(base['records'])
    corrected = {(r['datasetId'], r['frameIndex']): r for r in records}
    for e in entries:
        p.require(isinstance(e, dict) and type(e.get('frameIndex')) is int, 'Invalid review')
        key = (e.get('datasetId'), e.get('frameIndex'), e.get('physicalPaw'))
        p.require(key in index and key not in seen, 'Unknown/duplicate review label')
        seen.add(key)
        r = index[key]
        p.require(e.get('originalLabelSha256') == p.label_digest(r['human'][key[2]]) and
                  e.get('imageSha256') == r['imageSha256'], 'Stale label/image provenance')
        label = e.get('correctedLabel')
        p.require(isinstance(label, dict) and set(label) == {'status', 'x', 'y'}, 'Missing coordinate label')
        p.require(label['status'] in ('visible', 'occluded', 'unmarked', 'uncertain', 'ambiguous'), 'Invalid status')
        if label['status'] == 'visible':
            p.require(all(p.finite(label[c]) for c in ('x', 'y')) and
                      0 <= label['x'] < r['width'] and 0 <= label['y'] < r['height'], 'Invalid coordinate')
        else:
            p.require(label['x'] is None and label['y'] is None, 'Nonvisible coordinate')
        state, name = e.get('identityState'), e.get('anatomicalKeypoint')
        if 'bulkAssignmentId' in e or 'identitySource' in e:
            op = operation_index.get(e.get('bulkAssignmentId'))
            p.require(op is not None and e.get('identitySource') == 'human-confirmed-mapping', 'Missing human mapping audit')
            targets = {(a['datasetId'], a['frameIndex'], paw) for a in op['affected'] for paw in a['physicalPaws']}
            p.require(key in targets and state == 'verified' and name == BULK_MAPPING[key[2]] and
                      e['reviewer'] == op['reviewer'] and e['evidence'] == op['evidence'] and
                      e['correctedLabel'] == next(old['correctedLabel'] for old in op['beforeReviews']
                          if (old['datasetId'], old['frameIndex'], old['physicalPaw']) == key),
                      'Invalid bulk identity provenance')

        p.require(state in ('unreviewed', 'uncertain', 'verified'), 'Invalid identity state')
        p.require(name in (*p.ANATOMICAL, None), 'Invalid anatomical channel')
        p.require(type(e.get('landmarkConfirmed')) is bool and
                  type(e.get('continuityConfirmed')) is bool and type(e.get('modelExposed')) is bool,
                  'Missing review confirmations')
        p.require(all(isinstance(e.get(k), str) for k in ('reviewer', 'evidence')), 'Missing reviewer/evidence')
        changed = label != r['human'][key[2]]
        if changed or state == 'verified':
            p.require(e['reviewer'].strip() and e['evidence'].strip(), 'Review needs reviewer and evidence')
        if state == 'verified':
            p.require(name in p.ANATOMICAL and label['status'] == 'visible' and
                      e['landmarkConfirmed'] and e['continuityConfirmed'],
                      'Verified identity requires visible landmark and physical continuity')
            accepted[key] = copy.deepcopy(e)
        else:
            p.require(name is None, 'Unverified identity must have no anatomical channel')
        corrected[(key[0], key[1])]['human'][key[2]] = copy.deepcopy(label)
    p.require(seen == set(index), 'Missing review labels')
    for key, e in accepted.items():
        previous = accepted.get((key[0], key[1] - 1, key[2]))
        if previous:
            p.require(previous['anatomicalKeypoint'] == e['anatomicalKeypoint'],
                      'Conflicting identity across consecutive confirmed physical track labels')
    for r in records:
        names = [accepted[(r['datasetId'], r['frameIndex'], paw)]['anatomicalKeypoint']
                 for paw in p.PAWS if (r['datasetId'], r['frameIndex'], paw) in accepted]
        p.require(len(names) == len(set(names)), 'Conflicting A/B anatomical identities')
    names = [k['id'] for k in p.load_json(p.ROOT / 'training/canine_keypoint_schema.json')['keypoints']]
    payloads = {'review.json': copy.deepcopy(draft), 'corrected-physical-reference.json': records,
                'original-physical-reference.json': base['records'],
                'validation.json': identity_report(entries)}
    for split in p.SPLITS.values():
        payloads[f'{split}.coco.json'] = p.coco_export(records, accepted, names, split)
    encoded = {n: (json.dumps(v, indent=2, allow_nan=False) + '\n').encode() for n, v in payloads.items()}
    import hashlib
    encoded['manifest.json'] = json.dumps(dict(schemaVersion=2,
        createdAt=datetime.now(timezone.utc).isoformat(), referenceSha256=base['referenceSha256'],
        sourceConfiguration=base['sourceConfiguration'], exporterSha256=p.digest(Path(__file__)),
        verifiedPoints=len(accepted), outputSha256={n: hashlib.sha256(b).hexdigest() for n,b in encoded.items()}), indent=2).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in encoded.items():
            z.writestr(n, b)
    return result.getvalue()


def annotation_script(js):
    """Reuse the existing navigation/canvas with an isolated blind boot path."""
    p.require('const datasetBase=' in js and 'async function boot(){' in js and
              'boot().catch(error);' in js, 'Unsupported existing annotation UI')
    js = js.replace('const datasetBase=', "const datasetBase=new URLSearchParams(globalThis.location?.search||'').get('dataset')==='husky-evaluation'?'husky-evaluation/':", 1)
    js = js.replace('async function boot(){', "async function boot(){\n if(datasetBase==='husky-evaluation/')return pawReview.bootBlind();", 1)
    return js.replace('boot().catch(error);', 'boot().then(()=>pawReview.boot()).catch(error);')


def make_handler(get_base, blind_base=None, blind_frames=None):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(p.ROOT / UI), **kw)
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
            group = parse_qs(url.query).get('group', ['dalmatian'])[0]
            if url.path == '/api/session':
                if group == blind_review.GROUP:
                    if blind_base is None:
                        return self.send_bytes(b'Husky manifest not registered; start with --husky-manifest', 'text/plain', 404)
                    public = dict(blind_base, draft=blind_review.initial_draft(blind_base))
                    return self.send_bytes(json.dumps(public).encode(), 'application/json')
                base = get_base()
                return self.send_bytes(json.dumps(base).encode(), 'application/json')
            if url.path == '/dog02/manifest.json':
                base = get_base()
                spec = next(s for s in base['sourceConfiguration']['sequences'] if s['group'] == 'dog02')
                return self.send_bytes((p.ROOT / spec['metadata']['path']).read_bytes(), 'application/json')
            if url.path == '/api/predictions':
                if group == blind_review.GROUP:
                    return self.send_bytes(b'Predictions are disabled for blind Husky evaluation', 'text/plain', 403)
                base = get_base()
                spec = next((s for s in base['sourceConfiguration']['sequences'] if s['group'] == group), None)
                if spec is None:
                    return self.send_bytes(b'Unknown group', 'text/plain', 400)
                return self.send_bytes((p.ROOT / spec['predictions']['path']).read_bytes(), 'application/json')
            if url.path == '/review.js':
                return self.send_bytes((p.ROOT / 'training/paw-review.js').read_bytes(), 'text/javascript')
            if url.path in ('/', '/index.html'):
                html = (p.ROOT / UI / 'index.html').read_text()
                if blind_base is not None:
                    html = html.replace('Dataset: ', 'Dataset: <a href="?dataset=husky-evaluation">Husky: blind evaluation</a> · ', 1)
                html = html.replace('<script src="annotation.js', '<script src="/review.js"></script><script src="annotation.js')
                return self.send_bytes(html.encode(), 'text/html')
            if url.path == '/annotation.js':
                js = annotation_script((p.ROOT / UI / 'annotation.js').read_text())
                return self.send_bytes(js.encode(), 'text/javascript')
            if url.path == '/api/frame':
                try:
                    import cv2
                    q = parse_qs(url.query)
                    if group == blind_review.GROUP:
                        p.require(blind_base is not None and blind_frames is not None, 'Husky manifest not registered')
                        i = int(q['index'][0])
                        p.require(i in blind_frames, 'Invalid prepared Husky frame index')
                        return self.send_bytes(blind_frames[i], 'image/png')
                    base = get_base()
                    spec = next(s for s in base['sourceConfiguration']['sequences'] if s['group'] == q['group'][0])
                    meta = p.load_json(p.ROOT / spec['metadata']['path'])
                    i = int(q['index'][0])
                    p.require(0 <= i < meta['sourceFrameCount'], 'Invalid frame')
                    cap = cv2.VideoCapture(str(p.ROOT / spec['video']['path']))
                    try:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                        ok, frame = cap.read()
                        p.require(ok, 'Cannot decode frame')
                    finally:
                        cap.release()
                    ok, buf = cv2.imencode('.png', frame)
                    p.require(ok, 'Cannot encode frame')
                    r = next((r for r in base['records'] if r['group'] == spec['group'] and r['frameIndex'] == i), None)
                    if r:
                        import hashlib
                        p.require(hashlib.sha256(buf).hexdigest() == r['imageSha256'], 'Decoded image hash mismatch')
                    return self.send_bytes(buf.tobytes(), 'image/png')
                except Exception as exc:
                    return self.send_bytes(str(exc).encode(), 'text/plain', 400)
            return super().do_GET()
        def do_POST(self):
            try:
                url = urlsplit(self.path)
                p.require(url.path in ('/api/export', '/api/bulk-preview', '/api/bulk-apply', '/api/validate'), 'Unknown endpoint')
                size = int(self.headers.get('Content-Length', '0'))
                p.require(0 < size < 2_000_000, 'Invalid export size')
                draft = json.loads(self.rfile.read(size))
                group = parse_qs(url.query).get('group', ['dalmatian'])[0]
                if group == blind_review.GROUP:
                    p.require(blind_base is not None, 'Husky manifest not registered')
                    p.require(url.path in ('/api/export', '/api/validate'), 'Bulk mapping disabled for Husky')
                    if url.path == '/api/validate':
                        return self.send_bytes(json.dumps(blind_review.validate(blind_base, draft)).encode(), 'application/json')
                    payload = blind_review.export_review(blind_base, draft)
                    output = blind_review.save_export(payload, root=p.ROOT)
                    return self.send_bytes(payload, 'application/zip', headers={
                        'Content-Disposition': f'attachment; filename="{output.name}"',
                        'X-PetLens-Export-Path': str(output.relative_to(p.ROOT))})
                base = get_base()
                if url.path == '/api/validate':
                    return self.send_bytes(json.dumps(review_diagnostics(base, draft)).encode(), 'application/json')
                if url.path == '/api/bulk-preview':
                    return self.send_bytes(json.dumps(bulk_preview(base, draft)).encode(), 'application/json')
                if url.path == '/api/bulk-apply':
                    result = bulk_apply(base, draft['draft'], draft)
                    return self.send_bytes(json.dumps(result).encode(), 'application/json')
                return self.send_bytes(export_review(base, draft), 'application/zip')
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_bytes(str(exc).encode(), 'text/plain', 400)
    return Handler


def serve(port, husky_manifest=None):
    # Opening blind Husky review never loads the existing prediction/label session.
    existing = None
    def get_base():
        nonlocal existing
        if existing is None:
            existing = session()
            for r in existing['records']:
                r['labelHashes'] = {paw: p.label_digest(r['human'][paw]) for paw in p.PAWS}
        return existing
    blind_base, blind_frames = blind_review.session(husky_manifest) if husky_manifest else (None, None)
    Handler = make_handler(get_base, blind_base, blind_frames)
    print(f'Review: http://localhost:{port}/?dataset=dalmatian', flush=True)
    if blind_base:
        print(f'Blind Husky: http://localhost:{port}/?dataset=husky-evaluation', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--husky-manifest', type=Path, help='Register an isolated, verified blind Husky dataset')
    parser.add_argument('--preview-output', type=Path, help='Write a read-only bulk preview and exit')
    parser.add_argument('--draft', type=Path, help='Preview a saved review draft, preserving its decisions')
    parser.add_argument('--diagnostics-output', type=Path, help='Write read-only validation diagnostics and exit')
    parser.add_argument('--mapping-confirmation', type=Path, help='Recorded reviewer-provided mapping and evidence')
    parser.add_argument('--export-output', type=Path, help='Write a new validated ZIP using --mapping-confirmation')
    args = parser.parse_args()
    p.require(sum(bool(x) for x in (args.export_output, args.diagnostics_output, args.preview_output)) <= 1,
              'Choose one output mode')
    if args.export_output:
        p.require(args.mapping_confirmation is not None, 'Export requires --mapping-confirmation')
        base = session()
        if not args.draft:
            p.require(not p.load_json(p.ROOT / REFERENCE / 'accepted-anatomical-reviews.json'),
                      'Existing anatomical reviews found; supply a saved V2 draft to preserve them')
        draft = p.load_json(args.draft) if args.draft else initial_draft(base)
        result, payload = confirmed_mapping_export(base, draft, p.load_json(args.mapping_confirmation))
        with args.export_output.open('xb') as stream:
            stream.write(payload)
        print(f"Validated export: {args.export_output}; "
              f"verified points: {sum(e['identityState'] == 'verified' for e in result['reviews'])}")
    elif args.diagnostics_output:
        p.require(args.draft is not None, 'Diagnostics require --draft; browser autosaves are not accessible here')
        report = review_diagnostics(session(), p.load_json(args.draft))
        with args.diagnostics_output.open('x') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
        print(f"Valid: {report['valid']}; incomplete reviews: {len(report['incompleteReviews'])}")
    elif args.preview_output:
        base = session()
        draft = p.load_json(args.draft) if args.draft else initial_draft(base)
        preview = bulk_preview(base, draft)
        preview['draftSource'] = str(args.draft) if args.draft else 'Original source annotations; browser drafts are not accessible'
        preview['status'] = 'Awaiting explicit reviewer confirmation; no anatomical labels changed'
        preview['currentValidation'] = identity_report(draft['reviews'])
        args.preview_output.write_text(json.dumps(preview, indent=2) + '\n')
        print(f"{preview['annotationCount']} eligible annotations across {preview['frameCount']} frames")
    else:
        serve(args.port, args.husky_manifest)
