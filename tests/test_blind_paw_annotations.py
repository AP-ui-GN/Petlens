"""Blind Husky alignment, isolation, uncertainty and export regression tests."""
import copy
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from training import blind_paw_annotations as blind
from training import prepare_paw_annotations as p
from training import review_paw_annotations as review


def base_fixture():
    blank = dict(status='unmarked', x=None, y=None)
    record = dict(datasetId='husky-fixture', group=blind.GROUP, split='exploratory_evaluation',
                  frameIndex=0, timestampSeconds=0, width=100, height=80, imageSha256='image',
                  human=dict(A=copy.deepcopy(blank), B=copy.deepcopy(blank), modelExposed=False))
    return dict(schemaVersion=1, annotationType=blind.TYPE, blind=True,
                referenceSha256='reference', sourceConfiguration={'group': blind.GROUP}, records=[record])


class BlindExportTests(unittest.TestCase):
    def setUp(self):
        self.base = base_fixture()
        self.draft = blind.initial_draft(self.base)
        self.draft['reviewer'] = 'test human'

    def test_visible_uncertain_anatomy_survives_without_forced_mapping(self):
        e = self.draft['reviews'][0]
        e.update(correctedLabel=dict(status='visible', x=22.5, y=30), identityState='uncertain')
        self.draft['reviews'][1]['correctedLabel'] = dict(status='occluded', x=None, y=None)
        before = copy.deepcopy((self.base, self.draft))
        report = blind.validate(self.base, self.draft)
        self.assertEqual(report['visibilityCounts']['visible'], 1)
        with zipfile.ZipFile(io.BytesIO(blind.export_review(self.base, self.draft))) as z:
            self.assertEqual(set(z.namelist()), {'review.json', 'frame-manifest.json', 'validation.json', 'manifest.json'})
            exported = json.loads(z.read('review.json'))
            self.assertEqual(exported['reviews'][0], e)
            self.assertIsNone(exported['reviews'][0]['anatomicalKeypoint'])
            manifest = json.loads(z.read('manifest.json'))
            self.assertFalse(manifest['modelSelectionAllowed'])
            self.assertEqual(manifest['split'], 'exploratory_evaluation')
            for name, sha in manifest['outputSha256'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), sha)
        self.assertEqual((self.base, self.draft), before)

    def test_unreviewed_slots_are_preserved_and_reviewer_is_required(self):
        self.assertEqual(blind.validate(self.base, self.draft)['visibilityCounts']['unmarked'], 2)
        self.draft['reviewer'] = ''
        with self.assertRaises(p.ValidationError):
            blind.export_review(self.base, self.draft)

    def test_invalid_coordinates_exposure_and_provenance_rejected(self):
        mutations = [
            lambda d: d.update(referenceSha256='stale'),
            lambda d: d.update(blind=False),
            lambda d: d.update(bulkAssignments=[{'mapping': {'A': 'right_back_paw'}}]),
            lambda d: d['reviews'][0].update(datasetId='dalmatian'),
            lambda d: d['reviews'][0].update(frameIndex=1),
            lambda d: d['reviews'][0].update(imageSha256='stale'),
            lambda d: d['reviews'][0].update(originalLabelSha256='stale'),
            lambda d: d['reviews'][0].update(modelExposed=True),
            lambda d: d['reviews'][0].update(identitySource='human-confirmed-mapping'),
            lambda d: d['reviews'][0].update(correctedLabel=dict(status='visible', x=100, y=1)),
            lambda d: d['reviews'][0].update(correctedLabel=dict(status='visible', x=float('nan'), y=1)),
            lambda d: d['reviews'][0].update(correctedLabel=dict(status='occluded', x=1, y=1)),
            lambda d: d['reviews'].append(copy.deepcopy(d['reviews'][0])),
            lambda d: d['reviews'].pop(),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                draft = copy.deepcopy(self.draft)
                mutate(draft)
                with self.assertRaises(p.ValidationError):
                    blind.validate(self.base, draft)

    def test_anatomy_requires_evidence_and_uncertain_identity_has_no_channel(self):
        e = self.draft['reviews'][0]
        e.update(correctedLabel=dict(status='visible', x=20, y=30), identityState='verified',
                 anatomicalKeypoint='left_back_paw')
        with self.assertRaises(p.ValidationError):
            blind.validate(self.base, self.draft)
        e.update(landmarkConfirmed=True, continuityConfirmed=True, evidence='Human followed connected leg through context')
        self.assertEqual(blind.validate(self.base, self.draft)['anatomicallyAsserted'], 1)
        e['identityState'] = 'uncertain'
        with self.assertRaises(p.ValidationError):
            blind.validate(self.base, self.draft)

    def test_versioned_exports_are_isolated_and_never_overwritten(self):
        payload = blind.export_review(self.base, self.draft)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = blind.save_export(payload, root), blind.save_export(payload, root)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_relative_to(root / blind.EXPORTS))
            self.assertEqual(first.read_bytes(), payload)
            self.assertEqual(second.read_bytes(), payload)
            self.assertEqual(len(list(root.rglob('*.zip'))), 2)

    def test_http_blind_routes_never_load_legacy_session_or_predictions(self):
        get_base = MagicMock(side_effect=AssertionError('Legacy session must not be loaded'))
        handler = review.make_handler(get_base, self.base, {0: b'verified png bytes'})
        with tempfile.TemporaryDirectory() as temp, patch.object(p, 'ROOT', Path(temp)):
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(url + '/api/session?group=husky-evaluation') as response:
                    session = json.load(response)
                self.assertTrue(session['blind'])
                with urlopen(url + '/api/frame?group=husky-evaluation&index=0') as response:
                    self.assertEqual(response.read(), b'verified png bytes')
                with self.assertRaises(HTTPError) as error:
                    urlopen(url + '/api/predictions?group=husky-evaluation')
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    urlopen(url + '/api/frame?group=husky-evaluation&index=63')
                error.exception.close()
                request = Request(url + '/api/export?group=husky-evaluation',
                                  data=json.dumps(self.draft).encode(), method='POST')
                with urlopen(request) as response:
                    saved = Path(temp) / response.headers['X-PetLens-Export-Path']
                    self.assertEqual(saved.read_bytes(), response.read())
                self.assertTrue(saved.is_relative_to(Path(temp) / blind.EXPORTS))
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url + '/api/bulk-preview?group=husky-evaluation', data=json.dumps(self.draft).encode()))
                error.exception.close()
                get_base.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class AlignmentTests(unittest.TestCase):
    def test_exact_sample_verification_count_discrepancy_and_wrong_frame_rejection(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'package'
            (package / 'annotation_frames').mkdir(parents=True)
            video = package / 'video.mp4'
            video.write_bytes(b'saved video fixture')
            indices = list(range(0, 60, 3))
            images = [np.full((4, 6, 3), i, dtype=np.uint8) for i in range(63)]
            samples = []
            for i in indices:
                name = f'annotation_frames/frame_{i:03}.png'
                cv2.imwrite(str(package / name), images[i])
                samples.append(dict(frame_index_zero_based=i, source_time_seconds_approx=i / 10,
                                    file=name, annotation_status='not_reviewed'))
            preparation = dict(prepared_file='video.mp4', prepared_sha256=p.digest(video),
                source_file='unavailable.webm', source_sha256='source-claim',
                full_prepared_frame_count=63, prepared_video_size_px=[6, 4],
                annotated_frame_indices_zero_based=indices, method='Selected source frames 39 through 102 inclusive', limitations=[])
            (package / 'PREPARATION_MANIFEST.json').write_text(json.dumps(preparation))
            (package / 'FRAME_INDEX.json').write_text(json.dumps(samples))
            def capture(*args):
                cap = MagicMock()
                cap.isOpened.return_value = True
                index = [-1]
                def read():
                    index[0] += 1
                    return (True, images[index[0]]) if index[0] < 63 else (False, None)
                cap.read.side_effect = read
                cap.get.side_effect = lambda key: 64 if key == cv2.CAP_PROP_FRAME_COUNT else 10 if key == cv2.CAP_PROP_FPS else index[0] * 100
                return cap
            with patch.object(cv2, 'VideoCapture', side_effect=capture):
                output = root / 'manifest.json'
                manifest = blind.prepare(output, root, Path('package'))
                self.assertEqual(manifest['frameCountDiscrepancy']['impliedSourceFrameCount'], 64)
                self.assertEqual(manifest['frameCountDiscrepancy']['containerReportedFrameCount'], 64)
                self.assertEqual(manifest['frameCount'], 63)
                with self.assertRaises(p.ValidationError):
                    blind.prepare(output, root, Path('package'))
                base, encoded = blind.session(output, root)
                self.assertEqual(len(base['records']), 20)
                self.assertEqual(len(encoded), 63)
                cv2.imwrite(str(package / samples[0]['file']), images[1])
                with self.assertRaisesRegex(p.ValidationError, 'pixel mismatch'):
                    blind.inspect_package(root, Path('package'))


if __name__ == '__main__':
    unittest.main()
