"""Sparse human evidence, uncertainty and conflict must survive V3 export safely."""
from collections import Counter
import io
from pathlib import Path
import zipfile

import numpy as np

from training import gait_event_review as review
from training import prepare_contact_sequences as prep
from training import prepare_paw_annotations as p


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'reports/canine-contact-batch-v1'
DRAFTS = BATCH / 'drafts'
EXPECTED = {
    ('C', 4): ('unknown', 'unknown', None, False, None),
    ('C', 11): ('contacting', 'definite', None, False, 'high confidence'),
    ('C', 46): ('contacting', 'definite', 80, True, None),
    ('C', 50): ('airborne', 'definite', 100, False, None),
    ('D', 7): ('unknown', 'unknown', None, False, None),
    ('D', 13): ('airborne', 'provisional', None, False, 'moderate confidence'),
    ('D', 34): ('unknown', 'unknown', None, False, None),
    ('D', 41): ('contacting', 'definite', 95, False, None),
    ('A', 15): ('contacting', 'definite', 80, False, None),
    ('A', 20): ('airborne', 'definite', 100, False, None),
    ('A', 43): ('contacting', 'definite', None, False, 'pretty confident'),
    ('A', 50): ('contacting', 'definite', 100, False, None),
    ('B', 6): ('unknown', 'unknown', None, False, None),
    ('B', 9): ('contacting', 'definite', None, False, 'very confident'),
    ('B', 49): ('contacting', 'definite', None, False, None),
    ('B', 55): ('airborne', 'definite', 100, False, None),
}


def document(suffix, version=3):
    return p.load_json(DRAFTS / f's004-human-observations-v{version}.{suffix}')


def context():
    path = BATCH / 'frame-manifest.json'
    return p.load_json(path)['datasets']['gait-s004'], p.digest(path)


def test_exactly_16_source_aligned_observations_keep_reported_confidence():
    meta, sha = context()
    frames = document('frames.json')
    assert frames['manifestSha256'] == sha
    observed = frames['observations']
    assert len(observed) == 16
    assert {(r['physicalPaw'], r['frame']['frameIndex']) for r in observed} == set(EXPECTED)
    assert Counter(r['physicalPaw'] for r in observed) == dict.fromkeys('ABCD', 4)
    assert Counter(r['assessmentStatus'] for r in observed) == dict(definite=11, provisional=1, unknown=4)
    for record in observed:
        paw, i = record['physicalPaw'], record['frame']['frameIndex']
        state, status, percentage, approximate, qualitative = EXPECTED[paw, i]
        assert record['frame'] == meta['frames'][i]
        assert record['reportedSupportState'] == state
        assert record['assessmentStatus'] == status
        assert record['confidence']['percentage'] == percentage
        assert record['confidence']['approximate'] is approximate
        assert record['confidence']['qualitative'] == qualitative
        assert record['originalObservationVerbatim'].startswith(f'- Frame {i}: ')
        assert record['independentlyVerified'] is record['trainingApproved'] is False
        assert record['trainingEligibility']['approved'] is False
        assert record['frameSpecificIdentityExplicitlyConfirmed'] is (True if (paw, i) == ('C', 11) else None)


def test_reviewed_unknown_provisional_and_unverified_states_stay_distinct():
    meta, sha = context()
    draft = document('review.json')
    result = review.validate(meta, sha, draft)
    assert result['valid'] is True
    assert result['unreviewedPawFrames'] == 224
    assert result['humanAssertedCompleteStrides'] == 0
    assert result['independenceDeclared'] is result['adjudicated'] is False
    assert draft['strides'] == []
    states = Counter(o['supportState'] for paws in draft['observations'].values() for o in paws.values())
    assert states == dict(unreviewed=224, unknown=4, uncertain=1, contacting=8, airborne=3)
    for frame in range(60):
        for paw in 'ABCD':
            obs = draft['observations'][str(frame)][paw]
            if (paw, frame) not in EXPECTED:
                assert obs['supportState'] == obs['visibility'] == obs['continuity'] == 'unreviewed'
                continue
            state, status, *_ = EXPECTED[paw, frame]
            assert obs['supportState'] == ('uncertain' if status == 'provisional' else state)
            if status == 'unknown':
                assert obs['visibility'] == 'uncertain'
                assert obs['continuity'] == 'unreviewed'
            else:
                assert obs['visibility'] == 'visible'
                assert obs['continuity'] == 'continuous'
    provisional = next(r for r in document('frames.json')['observations'] if r['assessmentStatus'] == 'provisional')
    assert (provisional['physicalPaw'], provisional['frame']['frameIndex']) == ('D', 13)
    assert provisional['reportedSupportState'] == 'airborne'
    assert 'provisional_support_state' in provisional['trainingEligibility']['reasons']
    assert 'moderate confidence. Provisional.' in draft['observations']['13']['D']['notes']


def test_all_eight_event_records_are_unchanged_from_v2():
    events = document('events.json')
    prior = document('events.json', version=2)
    assert events['events'] == prior['events']
    assert len(events['events']) == 8
    assert Counter(event['physicalPaw'] for event in events['events']) == dict.fromkeys('ABCD', 2)
    assert events['originalV2EventRecordsUnchanged'] is True
    assert events['noNewEventsCreated'] is events['noCompleteStrideInferred'] is True
    for event in events['events']:
        assert event['exactTransitionFrame'] is None
        assert event['firstDefinitelyContacting'] is event['firstDefinitelyAirborne'] is None
        assert event['lastDefinitelyContacting'] is event['lastDefinitelyAirborne'] is None
    assert events['eventConflictReferences'] == {'A-contact-44-49': ['hind-A-contact-43-vs-touchdown-44-49']}


def test_hind_a43_contact_and_original_touchdown_range_remain_unresolved():
    conflicts = document('conflicts.json')
    frames = document('frames.json')
    events = document('events.json')
    assert conflicts['unresolvedConflictCount'] == len(conflicts['conflicts']) == 1
    conflict = conflicts['conflicts'][0]
    assert conflict['status'] == 'unresolved'
    assert conflict['resolution'] is None
    assert conflict['automaticResolution'] is False
    assert conflict['frame43Retained'] is conflict['originalRangeRetained'] is True
    assert conflict['frameEvidence']['frame']['frameIndex'] == 43
    assert conflict['eventEvidence']['frameRange'] == [44, 49]
    a43 = next(record for record in frames['observations'] if record['id'] == 'A-frame-43')
    assert a43['reportedSupportState'] == 'contacting'
    assert a43['assessmentStatus'] == 'definite'
    assert a43['confidence']['percentage'] is None
    assert a43['confidence']['qualitative'] == 'pretty confident'
    assert a43['conflicts'] == [conflict['id']]
    assert 'unresolved_event_frame_conflict' in a43['trainingEligibility']['reasons']
    assert document('review.json')['observations']['43']['A']['supportState'] == 'contacting'
    touchdown = next(event for event in events['events'] if event['id'] == 'A-contact-44-49')
    assert touchdown['humanReportedTimingWindow']['frameRange'] == [44, 49]
    assert conflict['targetedHumanCheck']['frameRange'] == [43, 49]
    for record in (conflicts['review'], conflicts['frameObservations'], conflicts['events'],
                   conflict['frameEvidence']['file'], conflict['eventEvidence']['file']):
        assert p.checked(ROOT, record).is_file()


def test_provenance_exposure_physical_ids_and_all_previous_versions_are_preserved():
    frames = document('frames.json')
    prior_files = frames['versioning']['previousVersionFiles']
    assert frames['versioning']['observationVersion'] == 3
    assert frames['versioning']['supersedesObservationVersion'] == 2
    actual = {path.name for version in (1, 2) for path in DRAFTS.glob(f's004-human-observations-v{version}.*')}
    assert set(prior_files) == actual
    assert len(prior_files) == 12
    for record in prior_files.values():
        assert p.checked(ROOT, record).is_file()
    assert frames['independenceDeclaration'] == document('review.json')['independenceDeclaration'] == 'prior_exposure'
    assert frames['exposure']['priorFootageExposure'] is frames['exposure']['priorAnnotationExposure'] is True
    assert frames['exposure']['sameHumanReviewerAs'] == document('review.json', version=2)['reviewer']
    assert document('review.json')['reviewer'] not in [document('review.json', version=v)['reviewer'] for v in (1, 2)]
    assert frames['physicalIdentity']['physicalIds'] == dict(A='Hind A', B='Hind B', C='Front C', D='Front D')
    assert frames['physicalIdentity']['anatomicalMapping'] == dict.fromkeys('ABCD')
    path = p.checked(ROOT, frames['provenance']['verbatimRecord'])
    original = path.read_text().split('\n## Encoding and evidence limits\n', 1)[0].rstrip() + '\n'
    assert frames['provenance']['originalObservationsVerbatim'] == original
    for record in frames['observations']:
        assert original.count(record['originalObservationVerbatim']) == 1
        assert record['originalObservationVerbatim'] in document('review.json')['observations'][str(record['frame']['frameIndex'])][record['physicalPaw']]['notes']
    for record in (frames['frameManifest'], frames['sourceVideo'], frames['review']):
        assert p.checked(ROOT, record).is_file()


def test_export_and_existing_adapter_keep_v3_non_independent_with_zero_training_targets():
    meta, sha = context()
    draft, frames = document('review.json'), document('frames.json')
    payload = review.export_review(meta, sha, draft)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert prep._json_bytes(archive.read('review.json')) == draft
        assert prep._json_bytes(archive.read('frame-manifest.json')) == meta
        envelope = prep._json_bytes(archive.read('manifest.json'))
        for name, digest in envelope['outputSha256'].items():
            assert review.digest_bytes(archive.read(name)) == digest
        result = prep._json_bytes(archive.read('validation.json'))
        assert result['independenceDeclared'] is result['adjudicated'] is False
    inputs = {}
    assert prep._load_review(ROOT, frames['review'], meta, sha, inputs) == draft
    path = DRAFTS / 's004-human-observations-v3.frames.json'
    exposure = dict(path=str(path.relative_to(ROOT)), sha256=p.digest(path))
    specs = [dict(pair=pair, mapping={}, reviews=[frames['review']], exposureRecords=[exposure])
             for pair in ('fore', 'hind')]
    labels, findings = prep._labels(ROOT, specs, meta, sha, dict(timestamps=np.arange(60) / 12), inputs)
    assert labels['target_valid'].shape == (60, 4)
    assert not labels['target_valid'].any()
    assert not labels['label_valid'].any()
    for finding in findings:
        assert finding['independent'] is finding['adjudicated'] is finding['mappingVerified'] is False
        assert finding['exposedReviewers'] == [draft['reviewer']]


def test_followup_prioritizes_conflict_without_repeating_completed_checks():
    checklist = document('verification.json')
    assert len(checklist['completedTargetedObservations']) == 16
    first = checklist['tasks'][0]
    assert first['priority'] == 1
    assert first['physicalPaw'] == 'A'
    assert first['frameRange'] == [43, 49]
    assert checklist['tasks'][1]['framesToCheck'] == [13]
    assert checklist['tasks'][1]['requiredNow'] is False
    assert checklist['interfaceChanged'] is checklist['automatedContactSuggestions'] is False
    for record in (checklist['events'], checklist['frameObservations'], checklist['conflicts'], checklist['supersedesChecklist']):
        assert p.checked(ROOT, record).is_file()
