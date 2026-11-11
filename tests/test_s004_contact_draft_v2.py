"""Corrected physical assignments preserve V1 evidence and never fabricate targets."""
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
EXPECTED = [
    ('A', 'lift_off', [16, 19]), ('A', 'contact', [44, 49]),
    ('B', 'contact', [7, 8]), ('B', 'lift_off', [50, 54]),
    ('C', 'contact', [5, 10]), ('C', 'lift_off', [47, 49]),
    ('D', 'lift_off', [8, 12]), ('D', 'contact', [35, 40]),
]


def document(version, suffix):
    return p.load_json(DRAFTS / f's004-human-observations-v{version}.{suffix}')


def context():
    path = BATCH / 'frame-manifest.json'
    return p.load_json(path)['datasets']['gait-s004'], p.digest(path)


def test_v2_intervals_directions_and_source_boundaries_match_human_correction():
    meta, sha = context()
    events = document(2, 'events.json')
    assert events['versioning']['observationVersion'] == 2
    assert events['manifestSha256'] == sha
    assert [(e['physicalPaw'], e['eventType'], e['humanReportedTimingWindow']['frameRange'])
            for e in events['events']] == EXPECTED
    assert events['physicalIdentity']['physicalIds'] == dict(
        A='Hind A', B='Hind B', C='Front C', D='Front D')
    assert events['physicalIdentity']['anatomicalMapping'] == dict.fromkeys('ABCD')
    for paw in 'ABCD':
        pair = [e for e in events['events'] if e['physicalPaw'] == paw]
        assert len(pair) == 2
        assert {e['eventType'] for e in pair} == {'contact', 'lift_off'}
        assert pair[0]['humanReportedTimingWindow']['frameRange'][1] < pair[1]['humanReportedTimingWindow']['frameRange'][0]
    for event in events['events']:
        window = event['humanReportedTimingWindow']
        lo, hi = window['frameRange']
        assert 0 <= lo <= hi <= 59
        assert window['inclusive'] is True
        assert window['start'] == meta['frames'][lo]
        assert window['end'] == meta['frames'][hi]
        assert event['transitionToState'] == ('contacting' if event['eventType'] == 'contact' else 'airborne')
        assert event['occurrence'] == 'human_confirmed'
        assert event['timingCertainty'] == 'interval_only'
        for key in ('exactTransitionFrame', 'lastDefinitelyAirborne', 'firstDefinitelyContacting',
                    'lastDefinitelyContacting', 'firstDefinitelyAirborne', 'reviewerRechecked'):
            assert event[key] is None
        assert event['automaticallyConfirmed'] is event['trainingApproved'] is False


def test_v1_all_files_stay_unchanged_and_supersession_is_explicit():
    events = document(2, 'events.json')
    versioning = events['versioning']
    assert versioning['observationVersion'] == 2
    assert versioning['supersedesObservationVersion'] == 1
    assert versioning['currentWorkingObservations'] is True
    files = versioning['version1Files']
    actual = {path.name for path in DRAFTS.glob('s004-human-observations-v1.*')}
    assert set(files) == actual
    assert len(files) == 6
    for record in files.values():
        assert p.checked(ROOT, record).is_file()
    assert p.checked(ROOT, versioning['supersedes']) == DRAFTS / 's004-human-observations-v1.events.json'
    old = {e['id']: e for e in document(1, 'events.json')['events']}
    for event in events['events']:
        lineage = event['version1Lineage']
        earlier = old[lineage['eventId']]
        assert earlier['humanReportedTimingWindow'] == event['humanReportedTimingWindow']
        assert earlier['eventType'] == event['eventType']
        expected_old = {'A': 'C', 'B': 'B', 'C': 'A', 'D': 'D'}[event['physicalPaw']]
        assert earlier['physicalPaw'] == lineage['previousPhysicalPaw'] == expected_old
        assert lineage['currentPhysicalPaw'] == event['physicalPaw']
        assert lineage['inheritedIndependentVerification'] is False
        assert lineage['historicalRecheckNotTransferred'] is (earlier['reviewerRechecked'] is True)


def test_unknown_draft_and_existing_export_do_not_create_ground_truth():
    meta, sha = context()
    draft = document(2, 'review.json')
    sidecar = document(2, 'events.json')
    result = review.validate(meta, sha, draft)
    assert result['valid'] is True
    assert result['humanAssertedCompleteStrides'] == 0
    assert result['independenceDeclared'] is result['adjudicated'] is False
    assert sidecar['trainingApproved'] is sidecar['adjudicated'] is False
    assert set(draft['observations']) == {str(i) for i in range(60)}
    assert draft['strides'] == []
    for paws in draft['observations'].values():
        assert set(paws) == set('ABCD')
        for obs in paws.values():
            assert obs['supportState'] == 'unknown'
            assert obs['visibility'] == obs['continuity'] == 'unreviewed'
    with zipfile.ZipFile(io.BytesIO(review.export_review(meta, sha, draft))) as archive:
        assert prep._json_bytes(archive.read('review.json')) == draft
        assert prep._json_bytes(archive.read('frame-manifest.json')) == meta
        assert prep._json_bytes(archive.read('validation.json')) == result


def test_same_reviewer_history_and_front_c_anchor_are_retained_verbatim():
    sidecar = document(2, 'events.json')
    old = document(1, 'review.json')
    draft = document(2, 'review.json')
    assert draft['reviewer'] != old['reviewer']  # Separate browser autosave key.
    assert sidecar['exposure']['sameHumanReviewerAs'] == old['reviewer']
    assert draft['independenceDeclaration'] == sidecar['independenceDeclaration'] == 'prior_exposure'
    assert sidecar['exposure']['priorFootageExposure'] is True
    assert sidecar['exposure']['priorAnnotationExposure'] is True
    assert sidecar['exposure']['previousAnnotationExposure'] is True
    assert sidecar['exposure']['independentlyVerified'] is False
    anchor = sidecar['physicalIdentity']['referenceAnchors']['C']
    assert anchor['descriptionVerbatim'] == "The reviewer described Front C as the paw closer to the dog's head in the stationary reference position."
    assert anchor['frameIndex'] is anchor['anatomicalSide'] is None
    assert anchor['descriptionVerbatim'] in draft['pawDescriptions']['C']
    provenance = sidecar['provenance']
    path = p.checked(ROOT, provenance['verbatimRecord'])
    verbatim = path.read_text().split('\n## Version and exposure record\n', 1)[0].rstrip() + '\n'
    assert provenance['originalObservationsVerbatim'] == verbatim
    assert '- The reviewer has previously seen and annotated S004.' in verbatim
    for record in (sidecar['review'], sidecar['frameManifest'], sidecar['sourceVideo']):
        assert p.checked(ROOT, record).is_file()


def test_existing_adapter_loads_v2_as_exposed_unmapped_and_all_masked():
    meta, sha = context()
    sidecar = document(2, 'events.json')
    path = DRAFTS / 's004-human-observations-v2.events.json'
    exposure = dict(path=str(path.relative_to(ROOT)), sha256=p.digest(path))
    specs = [dict(pair=pair, mapping={}, reviews=[sidecar['review']], exposureRecords=[exposure])
             for pair in ('fore', 'hind')]
    inputs = {}
    assert prep._load_review(ROOT, sidecar['review'], meta, sha, inputs) == document(2, 'review.json')
    labels, findings = prep._labels(ROOT, specs, meta, sha, dict(timestamps=np.arange(60) / 12), inputs)
    assert labels['target_valid'].shape == (60, 4)
    assert not labels['target_valid'].any()
    assert not labels['label_valid'].any()
    for finding in findings:
        assert finding['independent'] is finding['adjudicated'] is finding['mappingVerified'] is False
        assert finding['exposedReviewers'] == [sidecar['reviewer']]


def test_targeted_followup_uses_corrected_paws_and_two_decision_first_check():
    checklist = document(2, 'verification.json')
    meta, sha = context()
    assert checklist['observationVersion'] == 2
    assert checklist['manifestSha256'] == sha
    assert checklist['evidenceSource'] == meta['sourceVideo']
    assert checklist['interfaceChanged'] is checklist['automatedContactSuggestions'] is False
    first = checklist['tasks'][0]
    assert first['physicalPaw'] == 'C'
    assert first['framesToCheck'] == [4, 11]
    assert first['reportedTransitionRange'] == [5, 10]
    flanks = [task for task in checklist['tasks'] if task['id'].endswith('-flanks')]
    assert len(flanks) == 8
    assert sum(len(task['framesToCheck']) for task in flanks) == 16
    for task in flanks:
        lo, hi = task['reportedTransitionRange']
        assert (task['physicalPaw'], 'contact' if '-contact-' in task['id'] else 'lift_off', [lo, hi]) in EXPECTED
        assert task['framesToCheck'] == [lo - 1, hi + 1]
        assert task['requireExactTransitionFrame'] is False
    gaps = [task for task in checklist['tasks'] if task['id'].endswith('-intermediate')]
    assert [(t['physicalPaw'], t['frameRange']) for t in gaps] == [
        ('A', [20, 43]), ('B', [9, 49]), ('C', [11, 46]), ('D', [13, 34])]
    assert all(task['requiredForFirstTargetedPass'] is False for task in gaps)
    assert checklist['workload']['complete240LabelPassRequired'] is False
    assert checklist['reuse']['unchangedPaws'] == ['B', 'D']
    assert checklist['reuse']['independentEvidence'] is False
    assert checklist['draftImport']['sameHumanAsVersion1'] is True
    assert p.checked(ROOT, checklist['supersedesChecklist']).is_file()
