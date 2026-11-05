"""Review export safety, independent of the browser and model runtimes."""
import copy
import hashlib
import io
import json
import unittest
import zipfile
from training import review_paw_annotations as review
from training import prepare_paw_annotations as p


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        for group, split in p.SPLITS.items():
            self.records.append(dict(datasetId=group, group=group, split=split,
                frameIndex=1, width=100, height=80, imageSha256='image', fileName='image.png',
                human={paw:dict(status='visible', x=20 if paw=='A' else 60, y=30)
                       for paw in p.PAWS}))
        self.base = dict(schemaVersion=2, annotationType='anatomical-paw-review',
                         sourceConfiguration={'test':True}, referenceSha256='reference', records=self.records)
        self.draft = {k:copy.deepcopy(v) for k,v in self.base.items() if k!='records'}
        self.draft['reviews'] = [dict(datasetId=r['datasetId'], frameIndex=1,
            physicalPaw=paw, originalLabelSha256=p.label_digest(r['human'][paw]), imageSha256='image',
            correctedLabel=copy.deepcopy(r['human'][paw]), identityState='unreviewed', anatomicalKeypoint=None,
            reviewer='', evidence='', landmarkConfirmed=False, continuityConfirmed=False, modelExposed=False)
            for r in self.records for paw in p.PAWS]

    def verify(self, i=0, name='left_back_paw'):
        self.draft['reviews'][i].update(identityState='verified', anatomicalKeypoint=name,
            reviewer='person', evidence='Connected leg followed across frames 0–2; paw tip visible',
            landmarkConfirmed=True, continuityConfirmed=True)

    def files(self):
        with zipfile.ZipFile(io.BytesIO(review.export_review(self.base,self.draft))) as z:
            return {n:z.read(n) for n in z.namelist()}

    def reject(self):
        with self.assertRaises(p.ValidationError):
            review.export_review(self.base,self.draft)

    def test_unreviewed_and_uncertain_no_targets(self):
        self.draft['reviews'][0]['identityState']='uncertain'
        f=self.files()
        for split in p.SPLITS.values():
            self.assertEqual(json.loads(f[split+'.coco.json'])['annotations'],[])

    def test_conflicting_identity(self):
        self.verify();self.verify(1);self.reject()

    def test_consecutive_track_identity_conflict(self):
        r=copy.deepcopy(self.records[0]);r['frameIndex']=2;self.base['records'].append(r)
        for e in copy.deepcopy(self.draft['reviews'][:2]):
            e['frameIndex']=2;self.draft['reviews'].append(e)
        self.verify(0);self.verify(4,'right_back_paw');self.reject()

    def test_missing_label(self):
        self.draft['reviews'].pop();self.reject()

    def test_duplicate_label(self):
        self.draft['reviews'].append(copy.deepcopy(self.draft['reviews'][0]));self.reject()

    def test_coordinate_correction_and_integrity(self):
        self.verify();self.draft['reviews'][0]['correctedLabel']['x']=25.5
        before=copy.deepcopy(self.base);f=self.files()
        self.assertEqual(self.base,before)
        target=json.loads(f['train.coco.json'])['annotations'][0]
        self.assertEqual(target['keypoints'][39:42],[25.5,30,2])
        self.assertEqual(json.loads(f['exploratory_evaluation.coco.json'])['annotations'],[])
        for name,digest in json.loads(f['manifest.json'])['outputSha256'].items():
            self.assertEqual(hashlib.sha256(f[name]).hexdigest(),digest)
        self.assertEqual(json.loads(f['review.json']),self.draft)

    def test_correction_requires_provenance(self):
        self.draft['reviews'][0]['correctedLabel']['x']=25;self.reject()

    def test_diagnostics_lists_all_incomplete_records_without_mutation(self):
        self.draft['reviews'][0]['correctedLabel']['x'] = 25
        self.verify(1, 'right_back_paw')
        self.draft['reviews'][1].update(reviewer=' ', evidence='', continuityConfirmed=False)
        before = copy.deepcopy((self.base, self.draft))
        report = review.review_diagnostics(self.base, self.draft)
        self.assertFalse(report['valid'])
        self.assertEqual([e['missing'] for e in report['incompleteReviews']],
                         [['reviewer', 'evidence'], ['reviewer', 'evidence', 'continuityConfirmed']])
        self.assertEqual([e['physicalPaw'] for e in report['incompleteReviews']], ['A', 'B'])
        self.assertIn('dalmatian frame 1 paw A', report['errors'][0])
        self.assertIn('dalmatian frame 1 paw B', report['errors'][0])
        self.assertEqual((self.base, self.draft), before)
        self.reject()

    def test_diagnostics_checks_conflicts_and_preserves_uncertainty(self):
        self.draft['reviews'][0]['identityState'] = 'uncertain'
        before = copy.deepcopy(self.draft)
        self.assertTrue(review.review_diagnostics(self.base, self.draft)['valid'])
        self.assertEqual(self.draft, before)
        self.verify(0); self.verify(1)
        report = review.review_diagnostics(self.base, self.draft)
        self.assertFalse(report['valid'])
        self.assertEqual(report['incompleteReviews'], [])
        self.assertIn('Conflicting A/B', report['errors'][0])

    def test_missing_coordinate(self):
        self.verify();self.draft['reviews'][0]['correctedLabel']['x']=None;self.reject()

    def test_out_of_bounds(self):
        self.verify();self.draft['reviews'][0]['correctedLabel']['x']=100;self.reject()

    def test_hidden_or_ambiguous_never_verified(self):
        for status in ('occluded','ambiguous','uncertain','unmarked'):
            with self.subTest(status=status):
                self.verify();self.draft['reviews'][0]['correctedLabel']=dict(status=status,x=None,y=None);self.reject()

    def test_confirmations_required(self):
        for field in ('landmarkConfirmed','continuityConfirmed'):
            self.verify();self.draft['reviews'][0][field]=False;self.reject()

    def test_stale_hashes(self):
        for field in ('originalLabelSha256','imageSha256'):
            original=self.draft['reviews'][0][field]
            self.draft['reviews'][0][field]='wrong';self.reject()
            self.draft['reviews'][0][field]=original
        self.draft['referenceSha256']='wrong';self.reject()

    def test_uncertain_cannot_assert_channel(self):
        self.verify();self.draft['reviews'][0]['identityState']='uncertain';self.reject()

    def test_dog02_remains_exploratory(self):
        self.verify(2);f=self.files()
        self.assertEqual(json.loads(f['train.coco.json'])['annotations'],[])
        self.assertEqual(len(json.loads(f['exploratory_evaluation.coco.json'])['annotations']),1)


class BulkReviewTests(unittest.TestCase):
    files = ReviewTests.files
    reject = ReviewTests.reject
    def setUp(self):
        ReviewTests.setUp(self)
        template = copy.deepcopy(self.records[0])
        template['group'] = 'dalmatian'
        self.base['records'] = []
        self.draft['reviews'] = []
        for frame in range(45, 92):
            r = copy.deepcopy(template)
            r['frameIndex'] = frame
            r['human']['continuity'] = {paw: 'start' if frame == 46 else 'continuous' for paw in p.PAWS}
            self.base['records'].append(r)
            for paw in p.PAWS:
                self.draft['reviews'].append(dict(datasetId=r['datasetId'], frameIndex=frame,
                    physicalPaw=paw, originalLabelSha256=p.label_digest(r['human'][paw]), imageSha256='image',
                    correctedLabel=copy.deepcopy(r['human'][paw]), identityState='unreviewed', anatomicalKeypoint=None,
                    reviewer='', evidence='', landmarkConfirmed=False, continuityConfirmed=False, modelExposed=False))

    # These tests use a different fixture from the single-frame export tests.
    def test_bulk_preview_confirmation_and_audit(self):
        before = copy.deepcopy(self.draft)
        preview = review.bulk_preview(self.base, self.draft)
        self.assertEqual((preview['frameCount'], preview['annotationCount']), (45, 90))
        self.assertEqual(self.draft, before)
        request = dict(previewToken=preview['previewToken'], reviewer='human', evidence='Followed leg anatomy')
        for confirmation in (None, False, 'true'):
            with self.assertRaises(p.ValidationError):
                review.bulk_apply(self.base, self.draft, dict(request, confirmed=confirmation))
        self.draft = review.bulk_apply(self.base, self.draft, dict(request, confirmed=True))
        assigned = [e for e in self.draft['reviews'] if e['identityState'] == 'verified']
        self.assertEqual(len(assigned), 90)
        for e in assigned:
            self.assertEqual(e['anatomicalKeypoint'], review.BULK_MAPPING[e['physicalPaw']])
            self.assertEqual(e['identitySource'], 'human-confirmed-mapping')
        self.assertEqual(before['reviews'][0], self.draft['reviews'][0])
        self.assertEqual(before['reviews'][-1], self.draft['reviews'][-1])
        files = self.files()
        self.assertEqual(json.loads(files['original-physical-reference.json']), self.base['records'])
        self.assertEqual(json.loads(files['review.json'])['bulkAssignments'][0]['beforeReviews'], before['reviews'])
        self.assertEqual(review.bulk_preview(self.base, self.draft)['annotationCount'], 0)
        saved = copy.deepcopy(self.draft)
        self.draft['bulkAssignments'][0]['affected'][0]['physicalPaws'] = ['A']
        self.reject()
        self.draft = copy.deepcopy(saved)
        self.draft['reviews'][2]['correctedLabel']['x'] = 21
        self.reject()
        self.draft = copy.deepcopy(saved)
        self.draft.pop('bulkAssignments')
        self.reject()
        self.draft = saved
        self.draft['bulkAssignments'][0]['confirmed'] = False
        self.reject()

    def test_bulk_excludes_discontinuities_and_downstream(self):
        for state in ('broken', 'uncertain', 'unreviewed', 'swap', 'start'):
            with self.subTest(state=state):
                r = self.base['records'][5]  # frame 50
                r['human']['continuity']['B'] = state
                preview = review.bulk_preview(self.base, self.draft)
                self.assertEqual([a['frameIndex'] for a in preview['affected']], [46, 47, 48, 49])
        del self.base['records'][5]
        self.draft['reviews'] = [e for e in self.draft['reviews'] if e['frameIndex'] != 50]
        self.assertEqual(review.bulk_preview(self.base, self.draft)['frameCount'], 4)

    def test_bulk_preserves_decisions_corrections_and_hidden(self):
        es = [e for e in self.draft['reviews'] if e['frameIndex'] == 47]
        es[0].update(identityState='verified', anatomicalKeypoint='right_back_paw',
                     reviewer='prior', evidence='prior decision', landmarkConfirmed=True, continuityConfirmed=True)
        es[1]['correctedLabel']['x'] = 59
        es[1].update(reviewer='prior', evidence='correction')
        hidden = next(e for e in self.draft['reviews'] if e['frameIndex'] == 48)
        hidden['correctedLabel'] = dict(status='occluded', x=None, y=None)
        hidden.update(reviewer='prior', evidence='hidden paw')
        preview = review.bulk_preview(self.base, self.draft)
        self.assertEqual(preview['annotationCount'], 87)
        result = review.bulk_apply(self.base, self.draft, dict(previewToken=preview['previewToken'],
            confirmed=True, reviewer='new', evidence='anatomy'))
        for old in (*es, hidden):
            self.assertEqual(next(e for e in result['reviews'] if e['frameIndex']==old['frameIndex'] and e['physicalPaw']==old['physicalPaw']), old)

    def test_bulk_uncertainty_and_conflict_stop_mapping(self):
        e = next(e for e in self.draft['reviews'] if e['frameIndex']==50)
        e['identityState'] = 'uncertain'
        self.assertEqual(review.bulk_preview(self.base,self.draft)['frameCount'],4)
        e.update(identityState='verified', anatomicalKeypoint='left_back_paw', reviewer='prior',
                 evidence='opposite identity', landmarkConfirmed=True, continuityConfirmed=True)
        self.assertEqual(review.bulk_preview(self.base,self.draft)['frameCount'],4)
        e.update(identityState='unreviewed', anatomicalKeypoint=None)
        e['correctedLabel']=dict(status='ambiguous', x=None, y=None)
        self.assertEqual(review.bulk_preview(self.base,self.draft)['frameCount'],4)

    def test_bulk_rejects_stale_preview(self):
        preview = review.bulk_preview(self.base,self.draft)
        self.draft['reviews'][0]['evidence']='edited after preview'
        with self.assertRaises(p.ValidationError):
            review.bulk_apply(self.base,self.draft,dict(previewToken=preview['previewToken'],confirmed=True,
                reviewer='human', evidence='anatomy'))

    def test_reviewer_evidence_is_scoped_audited_and_cannot_override_uncertainty(self):
        evidence = p.load_json(p.ROOT / 'training/paw_bulk_continuity_evidence.json')
        evidence.update(referenceSha256=self.base['referenceSha256'],
                        datasetId=self.base['records'][0]['datasetId'])
        self.base['bulkContinuityEvidence'] = evidence
        r = next(r for r in self.base['records'] if r['frameIndex'] == 75)
        r['human']['continuity']['B'] = 'unreviewed'
        before = copy.deepcopy(self.draft)
        preview = review.bulk_preview(self.base, self.draft)
        self.assertEqual(preview['annotationCount'], 90)
        self.assertFalse(preview['continuityEvidence']['independentlyVerified'])
        self.assertEqual(self.draft, before)
        self.draft = review.bulk_apply(self.base, self.draft, dict(previewToken=preview['previewToken'],
            confirmed=True, reviewer='human', evidence='confirmed anatomy'))
        files = self.files()
        audit = json.loads(files['review.json'])['bulkAssignments'][0]
        self.assertEqual(audit['continuityEvidence'], evidence)
        self.assertEqual(json.loads(files['validation.json'])['duplicateAssignments'], 0)
        self.draft['bulkAssignments'][0]['continuityEvidence']['independentlyVerified'] = True
        self.reject()
        self.draft = before
        for state in ('broken', 'swap', 'uncertain'):
            r['human']['continuity']['B'] = state
            self.assertEqual(review.bulk_preview(self.base, self.draft)['frameCount'], 29)
        r['human']['continuity']['B'] = 'unreviewed'
        next(e for e in self.draft['reviews'] if e['frameIndex'] == 75)['identityState'] = 'uncertain'
        self.assertEqual(review.bulk_preview(self.base, self.draft)['frameCount'], 29)

    def test_real_source_preview_does_not_change_labels(self):
        base = review.session()
        draft = review.initial_draft(base)
        before = copy.deepcopy((base, draft))
        preview = review.bulk_preview(base, draft)
        self.assertEqual((preview['frameCount'], preview['annotationCount']), (42, 79))
        self.assertEqual(len(preview['excluded']), 11)
        self.assertEqual((base, draft), before)
        for missing in ('reviews',):
            bad = copy.deepcopy(draft)
            bad[missing].pop()
            with self.assertRaises(p.ValidationError):
                review.bulk_preview(base, bad)

    def test_direct_confirmed_export_preserves_real_coordinates_and_audit(self):
        base = review.session()
        draft = review.initial_draft(base)
        confirmation = p.load_json(p.ROOT / 'training/paw_anatomical_mapping_confirmation.json')
        before = copy.deepcopy((base, draft, confirmation))
        result, payload = review.confirmed_mapping_export(base, draft, confirmation)
        self.assertEqual((base, draft, confirmation), before)
        self.assertEqual([e['correctedLabel'] for e in result['reviews']],
                         [e['correctedLabel'] for e in draft['reviews']])
        from collections import Counter
        counts = Counter(e['anatomicalKeypoint'] for e in result['reviews'] if e['identityState'] == 'verified')
        self.assertEqual(counts, {'right_back_paw': 40, 'left_back_paw': 39})
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        for name, digest in json.loads(files['manifest.json'])['outputSha256'].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest)
        self.assertEqual(json.loads(files['review.json'])['reviewerProvidedConfirmation'], confirmation)
        self.assertEqual(json.loads(files['original-physical-reference.json']), base['records'])
        self.assertEqual(json.loads(files['exploratory_evaluation.coco.json'])['annotations'], [])

    def test_direct_export_rejects_uncertainty_conflicts_and_missing_evidence(self):
        base = review.session()
        confirmation = p.load_json(p.ROOT / 'training/paw_anatomical_mapping_confirmation.json')
        for state in ('uncertain', 'conflict', 'missing-evidence'):
            with self.subTest(state=state):
                draft = review.initial_draft(base)
                e = next(e for e in draft['reviews'] if e['frameIndex'] == 50 and e['physicalPaw'] == 'A')
                e['identityState'] = 'uncertain'
                if state != 'uncertain':
                    e.update(identityState='verified', anatomicalKeypoint='left_back_paw',
                             landmarkConfirmed=True, continuityConfirmed=True,
                             reviewer='prior reviewer', evidence='prior decision')
                    if state == 'missing-evidence':
                        e['evidence'] = ''
                before = copy.deepcopy(draft)
                with self.assertRaises(p.ValidationError):
                    review.confirmed_mapping_export(base, draft, confirmation)
                self.assertEqual(draft, before)


if __name__=='__main__':
    unittest.main()
