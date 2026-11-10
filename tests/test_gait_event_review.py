"""Human event-review isolation, source binding, and non-forced exports."""
import copy
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

import pytest

from training import gait_event_review as review
from training import prepare_paw_annotations as p


def fixture():
    meta = dict(group='gait-dalmatian', datasetId='fixture', sourceVideo=dict(path='original.mp4', sha256='video'),
        frameWidth=100, frameHeight=80, frameCount=8, reviewStart=0, reviewEnd=7,
        selectedFrames=list(range(8)), frames=[dict(frameIndex=i, timestampSeconds=i / 10,
            originalPts=i, originalTimeBase='1/10', imageSha256='image', pixelSha256='pixels') for i in range(8)])
    draft = review.initial_draft(meta, 'manifest')
    draft.update(reviewer='independent human', independenceDeclaration='no_prior_exposure')
    return meta, draft


def complete_draft():
    meta, draft = fixture()
    draft['pawDescriptions']['A'] = 'Human followed the near physical hind limb.'
    for i in range(1, 7):
        draft['observations'][str(i)]['A'].update(visibility='visible', continuity='continuous',
            supportState='contacting' if i in (2, 3, 6) else 'airborne')
    draft['strides'] = [dict(id='human-assertion', physicalPaw='A', status='complete', notes='Human source-frame evidence.',
        boundaries={key: dict(frameIndex=i, timestampSeconds=meta['frames'][i]['timestampSeconds'])
                    for i, (key, _) in enumerate(review.BOUNDARIES, 1)})]
    return meta, draft


def test_initial_draft_is_blank_and_not_an_adjudicated_reference():
    meta, _ = fixture()
    draft = review.initial_draft(meta, 'manifest')
    assert draft['strides'] == []
    assert draft['pawDescriptions'] == {'A': '', 'B': ''}
    assert all(o['visibility'] == o['continuity'] == o['supportState'] == 'unreviewed'
               for paws in draft['observations'].values() for o in paws.values())
    result = review.validate(meta, 'manifest', draft)
    assert result['humanAssertedCompleteStrides'] == 0
    assert result['adjudicated'] is False
    with pytest.raises(p.ValidationError, match='Reviewer'):
        review.export_review(meta, 'manifest', draft)


def test_partial_uncertain_and_occluded_reviews_can_export_without_inventing_events():
    meta, draft = fixture()
    draft['observations']['3']['A'].update(visibility='occluded', supportState='occluded', continuity='uncertain')
    draft['strides'] = [dict(id='uncertain', physicalPaw='A', status='unassessable',
        notes='Ground edge hidden', boundaries={key: None for key, _ in review.BOUNDARIES})]
    original = copy.deepcopy((meta, draft))
    with zipfile.ZipFile(io.BytesIO(review.export_review(meta, 'manifest', draft))) as archive:
        assert json.loads(archive.read('review.json')) == draft
        report = json.loads(archive.read('validation.json'))
        assert report['humanAssertedCompleteStrides'] == 0
        assert report['adjudicated'] is False
        manifest = json.loads(archive.read('manifest.json'))
        for name, sha in manifest['outputSha256'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == sha
        assert json.loads(archive.read('frame-manifest.json')) == meta
    assert (meta, draft) == original


def test_complete_is_a_human_assertion_and_source_times_are_preserved():
    meta, draft = complete_draft()
    report = review.validate(meta, 'manifest', draft)
    assert report['humanAssertedCompleteStrides'] == 1
    assert report['adjudicated'] is False
    assert report['independenceDeclared'] is True


@pytest.mark.parametrize('field,value', [
    ('manifestSha256', 'stale'), ('datasetId', 'other-source'), ('blind', False),
    ('modelExposed', True), ('previousLabelsExposed', True), ('predictionEvents', []),
])
def test_foreign_or_exposed_reviews_cannot_be_imported(field, value):
    meta, draft = fixture()
    draft[field] = value
    with pytest.raises(p.ValidationError):
        review.validate(meta, 'manifest', draft)


@pytest.mark.parametrize('mutation', [
    lambda d: d['strides'][0]['boundaries']['initialContactLastAirborne'].update(timestampSeconds=999),
    lambda d: d['strides'][0]['boundaries']['initialContactLastAirborne'].update(frameIndex=99),
    lambda d: d['strides'][0]['boundaries'].update(liftOffFirstAirborne=None),
    lambda d: d['strides'][0]['boundaries'].update(nextContactFirstContacting=dict(frameIndex=4, timestampSeconds=.4)),
    lambda d: d['observations']['4']['A'].update(visibility='occluded', supportState='occluded'),
    lambda d: d['observations']['4']['A'].update(continuity='uncertain'),
    lambda d: d['observations']['4']['A'].update(continuity='broken'),
    lambda d: d['observations']['4']['A'].update(supportState='unreviewed'),
    lambda d: d['observations'].pop('4'),
    lambda d: d['pawDescriptions'].update(A=''),
    lambda d: d['strides'].append(copy.deepcopy(d['strides'][0])),
    lambda d: d['strides'].append(dict(copy.deepcopy(d['strides'][0]), id='overlap')),
    lambda d: d['strides'].append(None),
])
def test_unsupported_complete_assertions_are_rejected(mutation):
    meta, draft = complete_draft()
    mutation(draft)
    with pytest.raises(p.ValidationError):
        review.validate(meta, 'manifest', draft)


def test_declared_prior_exposure_is_retained_but_not_independent():
    meta, draft = fixture()
    draft['independenceDeclaration'] = 'prior_exposure'
    assert review.validate(meta, 'manifest', draft)['independenceDeclared'] is False
    assert review.export_review(meta, 'manifest', draft)


def test_exports_are_new_files_and_never_overwrite_reviews():
    with tempfile.TemporaryDirectory() as tmp:
        first = review.save_export(b'first human review', Path(tmp))
        second = review.save_export(b'second human review', Path(tmp))
        assert first != second
        assert first.read_bytes() == b'first human review'
        assert second.read_bytes() == b'second human review'


def test_manifest_changes_block_source_session(monkeypatch, tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'stale': True}))
    monkeypatch.setattr(review, 'inspect_sources', lambda root: ({'actual': True}, {}))
    with pytest.raises(p.ValidationError, match='changed'):
        review.session(Path('manifest.json'), tmp_path)


def selected_session_fixture(tmp_path, monkeypatch):
    meta, _ = fixture()
    meta.update(group='gait-dog02', datasetId='verified-dog02')
    other = dict(copy.deepcopy(meta), group='gait-dalmatian', datasetId='blocked-dalmatian')
    stored = dict(schemaVersion=1, annotationType=review.TYPE,
                  datasets={'gait-dog02': meta, 'gait-dalmatian': other})
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(stored))
    actual = dict(stored, datasets={'gait-dog02': copy.deepcopy(meta)})
    calls = []

    def inspect(root, groups=None):
        calls.append((root, groups))
        assert groups == ('gait-dog02',), 'Unrelated source must not be decoded'
        return actual, {'gait-dog02': {0: b'verified image'}}

    monkeypatch.setattr(review, 'inspect_sources', inspect)
    return path, stored, actual, calls


def test_selected_session_verifies_only_requested_dataset_and_retains_manifest_hash(tmp_path, monkeypatch):
    path, stored, actual, calls = selected_session_fixture(tmp_path, monkeypatch)
    before = path.read_bytes()
    manifest, images, sha = review.session(path, tmp_path, group='gait-dog02')
    assert manifest == actual
    assert set(manifest['datasets']) == set(images) == {'gait-dog02'}
    assert sha == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before
    assert calls == [(tmp_path, ('gait-dog02',))]
    assert 'gait-dalmatian' in stored['datasets']


@pytest.mark.parametrize('field', [
    'sourceVideo', 'frameCount', 'frameWidth', 'frameHeight', 'selectedFrames',
    'reviewStart', 'reviewEnd', 'frameIndex', 'timestampSeconds', 'originalPts',
    'originalTimeBase', 'pixelSha256', 'imageSha256',
])
def test_selected_dataset_still_requires_every_provenance_field(tmp_path, monkeypatch, field):
    path, _, actual, _ = selected_session_fixture(tmp_path, monkeypatch)
    meta = actual['datasets']['gait-dog02']
    if field in meta:
        meta[field] = 'changed'
    else:
        meta['frames'][0][field] = 'changed'
    with pytest.raises(p.ValidationError, match='gait-dog02: provenance validation failed'):
        review.session(path, tmp_path, group='gait-dog02')


def test_selected_dataset_decoder_failure_is_named_and_blocks_startup(tmp_path, monkeypatch):
    path, _, _, _ = selected_session_fixture(tmp_path, monkeypatch)

    def broken(*args, **kwargs):
        raise OSError('source missing')

    monkeypatch.setattr(review, 'inspect_sources', broken)
    with pytest.raises(p.ValidationError, match='gait-dalmatian: provenance validation failed: source missing'):
        review.session(path, tmp_path, group='gait-dalmatian')


def test_selected_dalmatian_pixel_mismatch_still_fails_closed(tmp_path, monkeypatch):
    path, stored, _, _ = selected_session_fixture(tmp_path, monkeypatch)
    actual = dict(stored, datasets={'gait-dalmatian': copy.deepcopy(stored['datasets']['gait-dalmatian'])})
    actual['datasets']['gait-dalmatian']['frames'][0]['pixelSha256'] = 'decoder mismatch'
    monkeypatch.setattr(review, 'inspect_sources', lambda root, groups: (actual, {}))
    with pytest.raises(p.ValidationError, match='gait-dalmatian: provenance validation failed'):
        review.session(path, tmp_path, group='gait-dalmatian')


@pytest.mark.parametrize('group', ['gait-dalmatian', 'gait-dog02'])
def test_http_uses_allowlist_and_never_serves_legacy_labels_or_models(tmp_path, group):
    meta, draft = fixture()
    meta['group'] = group
    for relative in [review.UI / 'index.html', review.UI / 'annotation.js', Path('training/gait-event-review.js')]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p.ROOT / relative, target)
    manifest = dict(datasets={group: meta})
    server = ThreadingHTTPServer(('127.0.0.1', 0),
        review.make_handler(manifest, {group: {0: b'original pixels'}}, 'manifest', tmp_path))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(url + '/api/session?group=' + group) as response:
            assert json.load(response)['draft']['strides'] == []
        with urlopen(url + '/') as response:
            assert response.url.endswith('/?dataset=' + group)
            html = response.read().decode()
            assert 'id="adjudication"' not in html
            assert 'gait-event-review.js' in html
        with urlopen(url + '/annotation.js') as response:
            js = response.read().decode()
            assert 'gaitEventReview.boot().catch(error);' in js
            assert '\nboot().catch(error);' not in js
        for path in ['/api/predictions?group=gait-dalmatian', '/dalmatian/model-review.json',
                     '/dalmatian/manifest.json', '/api/session?group=dalmatian',
                     '/training/paw_annotation_sources.json', '/physical-tracks.js']:
            with pytest.raises(HTTPError) as error:
                urlopen(url + path)
            assert error.value.code in (400, 403, 404)
            error.value.close()
        blocked = next(key for key in review.SOURCES if key != group)
        for route in ['/?dataset=' + blocked, '/index.html?dataset=' + blocked,
                      '/api/session?group=' + blocked, '/api/frame?group=' + blocked + '&index=0',
                      '/api/validate?group=' + blocked, '/api/export?group=' + blocked]:
            request = (Request(url + route, method='POST', data=b'{}')
                       if route.startswith(('/api/validate', '/api/export')) else url + route)
            with pytest.raises(HTTPError) as error:
                urlopen(request)
            assert error.value.code == 409
            assert (blocked + ': access blocked').encode() in error.value.read()
            error.value.close()
        assert not (tmp_path / review.DIRECTORY / 'reviews').exists()
        with urlopen(url + '/api/frame?group=' + group + '&index=0') as response:
            assert response.read() == b'original pixels'
        with pytest.raises(HTTPError) as error:
            urlopen(url + '/api/frame?group=' + group + '&index=8')
        error.value.close()
        request = Request(url + '/api/export?group=' + group, method='POST', data=json.dumps(draft).encode())
        with urlopen(request) as response:
            target = tmp_path / response.headers['X-PetLens-Export-Path']
            assert target.read_bytes() == response.read()
    finally:
        server.shutdown(); server.server_close(); worker.join()
