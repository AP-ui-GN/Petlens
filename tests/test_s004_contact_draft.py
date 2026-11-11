"""Source-bound human interval evidence must never fabricate frame supervision."""
import io
import json
from pathlib import Path
import zipfile

import numpy as np

from training import gait_event_review as review
from training import prepare_contact_sequences as prep
from training import prepare_paw_annotations as p


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'reports/canine-contact-batch-v1'
STEM = BATCH / 'drafts/s004-human-observations-v1'


def documents():
    manifest_path = BATCH / 'frame-manifest.json'
    meta = p.load_json(manifest_path)['datasets']['gait-s004']
    draft = p.load_json(Path(str(STEM) + '.review.json'))
    sidecar = p.load_json(Path(str(STEM) + '.events.json'))
    return meta, p.digest(manifest_path), draft, sidecar


def test_s004_original_source_and_every_frame_still_match_saved_manifest():
    manifest, images, sha = review.session(
        BATCH / 'frame-manifest.json', root=ROOT, group='gait-s004')
    meta, expected_sha, _, sidecar = documents()
    assert sha == expected_sha == sidecar['manifestSha256']
    assert manifest['datasets']['gait-s004'] == meta
    assert (meta['frameWidth'], meta['frameHeight']) == (960, 544)
    assert meta['selectedFrames'] == list(range(60))
    for i, frame in enumerate(meta['frames']):
        assert frame['frameIndex'] == frame['originalPts'] == i
        assert frame['originalTimeBase'] == '1/12'
        assert frame['timestampSeconds'] == i / 12
        assert review.digest_bytes(images['gait-s004'][i]) == frame['imageSha256']


def test_all_eight_human_events_keep_uncertain_boundaries_and_physical_ids():
    meta, _, _, sidecar = documents()
    expected = [
        ('A', 'contact', [5, 10]), ('A', 'lift_off', [47, 49]),
        ('B', 'contact', [7, 8]), ('B', 'lift_off', [50, 54]),
        ('C', 'lift_off', [16, 19]), ('C', 'contact', [44, 49]),
        ('D', 'lift_off', [8, 12]), ('D', 'contact', [35, 40]),
    ]
    assert [(e['physicalPaw'], e['eventType'], e['humanReportedTimingWindow']['frameRange'])
            for e in sidecar['events']] == expected
    assert sidecar['physicalIdentity']['physicalIds'] == {
        'A': 'Hind A', 'B': 'Hind B', 'C': 'Front C', 'D': 'Front D'}
    assert sidecar['physicalIdentity']['anatomicalMapping'] == dict.fromkeys('ABCD')
    for event in sidecar['events']:
        window = event['humanReportedTimingWindow']
        lo, hi = window['frameRange']
        assert window['inclusive'] is True
        assert window['start'] == meta['frames'][lo]
        assert window['end'] == meta['frames'][hi]
        assert event['occurrence'] == 'human_confirmed'
        assert event['timingCertainty'] == 'interval_only'
        for field in ('exactTransitionFrame', 'lastDefinitelyAirborne',
                      'firstDefinitelyContacting', 'lastDefinitelyContacting',
                      'firstDefinitelyAirborne'):
            assert event[field] is None
        assert event['automaticallyConfirmed'] is event['trainingApproved'] is False
        assert event['reviewerRechecked'] is (True if event['physicalPaw'] == 'A' else None)


def test_unknown_draft_round_trip_is_valid_non_independent_and_not_ground_truth():
    meta, sha, draft, sidecar = documents()
    report = review.validate(meta, sha, draft)
    assert report['valid'] is True
    assert report['independenceDeclared'] is report['adjudicated'] is False
    assert report['humanAssertedCompleteStrides'] == 0
    assert draft['independenceDeclaration'] == 'prior_exposure'
    assert sidecar['exposure']['priorFootageExposure'] is True
    assert sidecar['trainingApproved'] is sidecar['adjudicated'] is False
    assert draft['strides'] == []
    assert set(draft['observations']) == {str(i) for i in range(60)}
    for paws in draft['observations'].values():
        assert set(paws) == set('ABCD')
        for observation in paws.values():
            assert observation['supportState'] == 'unknown'
            assert observation['visibility'] == observation['continuity'] == 'unreviewed'
    with zipfile.ZipFile(io.BytesIO(review.export_review(meta, sha, draft))) as archive:
        assert json.loads(archive.read('review.json')) == draft
        assert json.loads(archive.read('validation.json')) == report
        envelope = json.loads(archive.read('manifest.json'))
        for name, digest in envelope['outputSha256'].items():
            assert review.digest_bytes(archive.read(name)) == digest


def test_verbatim_provenance_and_earlier_records_are_preserved_by_hash():
    _, _, _, sidecar = documents()
    provenance = sidecar['provenance']
    text_path = p.checked(ROOT, provenance['verbatimRecord'])
    assert text_path.read_text() == provenance['originalObservationsVerbatim']
    assert 'Reviewer rechecked the Hind A observations and confirmed the recorded intervals.' in text_path.read_text()
    assert 'Do not describe this review as independent or first-time.' in text_path.read_text()
    for record in (sidecar['frameManifest'], sidecar['sourceVideo'], sidecar['review'],
                   *sidecar['previousAnnotations']['inspectedRecords']):
        assert p.checked(ROOT, record).is_file()
    assert sidecar['previousAnnotations']['liveBrowserStorageAccessed'] is False
    assert sidecar['previousAnnotations']['sameSourceSavedHumanAnnotationsFound'] is False


def test_existing_training_loader_preserves_draft_and_masks_every_target():
    meta, sha, draft, sidecar = documents()
    inputs = {}
    assert prep._load_review(ROOT, sidecar['review'], meta, sha, inputs) == draft
    sidecar_path = Path(str(STEM) + '.events.json')
    exposure = dict(path=str(sidecar_path.relative_to(ROOT)), sha256=p.digest(sidecar_path))
    # No anatomical assignment: retain C/D rather than silently projecting to A/B.
    specs = [dict(pair=pair, mapping={}, reviews=[sidecar['review']],
                  exposureRecords=[exposure]) for pair in ('hind', 'fore')]
    labels, findings = prep._labels(
        ROOT, specs, meta, sha, dict(timestamps=np.arange(60) / 12), inputs)
    assert labels['target_valid'].shape == (60, 4)
    assert not labels['target_valid'].any()
    assert not labels['label_valid'].any()
    assert np.all(labels['target_reasons'] == 'anatomical_mapping_unverified')
    for finding in findings:
        assert finding['independent'] is finding['adjudicated'] is finding['mappingVerified'] is False
        assert finding['exposedReviewers'] == [draft['reviewer']]


def test_targeted_checklist_preserves_manifest_and_hind_a_recheck():
    meta, sha, _, sidecar = documents()
    checklist = p.load_json(Path(str(STEM) + '.verification.json'))
    assert checklist['manifestSha256'] == sha
    assert checklist['evidenceSource'] == meta['sourceVideo']
    assert checklist['interfaceChanged'] is checklist['automatedContactSuggestions'] is False
    priorities = [t for t in checklist['tasks'] if t['priority'] == 1]
    assert [(t['physicalPaw'], t['frameRange']) for t in priorities] == [
        ('A', [11, 46]), ('B', [9, 49]), ('C', [20, 43]), ('D', [13, 34])]
    flanks = [t for t in checklist['tasks'] if t['id'].endswith('-flanks')]
    assert len(flanks) == len(sidecar['events']) == 8
    for task in flanks:
        lo, hi = task['reportedTransitionRange']
        assert task['framesToCheck'] == [lo - 1, hi + 1]
        if task['physicalPaw'] == 'A':
            assert task['occurrenceReconfirmationRequired'] is False
