"""Compact, timestamped motion trace output."""

import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import cv2
import numpy as np

from gait_engine.motion import compact_motion_trace, read_motion_signal


class MotionTraceTests(unittest.TestCase):
    def test_keeps_frame_pair_times_and_values_for_short_clips(self):
        trace = compact_motion_trace([0.1, 0.3, 0.5], 2.0)

        self.assertEqual(trace["sampleCount"], 3)
        self.assertEqual(
            trace["points"],
            [
                {"timeSeconds": 0.25, "movement": 0.1},
                {"timeSeconds": 0.75, "movement": 0.3},
                {"timeSeconds": 1.25, "movement": 0.5},
            ],
        )

    def test_downsamples_without_losing_the_raw_sample_count(self):
        trace = compact_motion_trace([float(index) / 1000 for index in range(240)], 24)

        self.assertEqual(trace["sampleCount"], 240)
        self.assertEqual(len(trace["points"]), 120)
        self.assertAlmostEqual(trace["points"][0]["movement"], 0.0005)
        self.assertAlmostEqual(trace["points"][-1]["movement"], 0.2385)

    def test_unknown_fps_retains_count_but_never_fabricates_time(self):
        trace = compact_motion_trace([0.1, 0.2], 0)

        self.assertEqual(trace, {"sampleCount": 2, "points": [], "timingSource": "unavailable"})

    def test_variable_source_times_override_nominal_fps(self):
        # These intervals cannot be recovered by dividing an index by FPS.
        trace = compact_motion_trace([0.1, 0.3, 0.5], 30,
                                     frame_times_seconds=[0, 0.04, 0.12, 0.4])
        self.assertEqual(trace["timingSource"], "decoder")
        self.assertEqual([p["timeSeconds"] for p in trace["points"]], [0.02, 0.08, 0.26])
        compacted = compact_motion_trace([0.1, 0.3, 0.5], 30, max_points=1,
                                         frame_times_seconds=[0, 0.04, 0.12, 0.4])
        self.assertEqual(compacted["points"], [{"timeSeconds": 0.2, "movement": 0.3}])

    def test_valid_source_times_work_without_nominal_fps(self):
        trace = compact_motion_trace([0.1], 0, frame_times_seconds=[0, 0.08])
        self.assertEqual(trace["timingSource"], "decoder")
        self.assertEqual(trace["points"], [{"timeSeconds": 0.04, "movement": 0.1}])

    def test_invalid_decoder_times_never_fall_back_to_frame_indices(self):
        for times in ([], [0], [0, 0, 0], [0, 0.1, 0.05],
                      [0, float("nan"), 0.2], [0.1, 0.2, 0.3], [0, 0.1, float("inf")]):
            with self.subTest(times=times):
                trace = compact_motion_trace([0.1, 0.2], 30, frame_times_seconds=times)
                self.assertEqual(trace, {"sampleCount": 2, "points": [], "timingSource": "unavailable"})

    def test_legacy_fps_estimates_are_explicitly_distinguished(self):
        self.assertEqual(compact_motion_trace([0.1], 12)["timingSource"], "nominal-fps")

    def test_reader_retains_decoder_times_instead_of_reconstructing_them(self):
        times = [0, 40, 120, 400]
        class Capture:
            index = -1
            released = False
            def isOpened(self): return True
            def get(self, key):
                return 30 if key == cv2.CAP_PROP_FPS else times[self.index]
            def read(self):
                self.index += 1
                return (True, np.zeros((16, 16, 3), dtype=np.uint8)) if self.index < 4 else (False, None)
            def release(self): self.released = True
        capture = Capture()
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / 'variable.mp4'
            video.touch()
            with patch('gait_engine.motion.cv2.VideoCapture', return_value=capture):
                signal = read_motion_signal(video)
        self.assertEqual(signal.frame_times_seconds, [0, 0.04, 0.12, 0.4])
        self.assertEqual(len(signal.frame_motion), 3)
        self.assertTrue(capture.released)

    def test_real_s004_has_60_frames_and_59_source_intervals(self):
        source = Path(__file__).parent / 'Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv'
        if not source.is_file():
            self.skipTest('Local S004 is unavailable')
        signal = read_motion_signal(source)
        trace = compact_motion_trace(signal.frame_motion, signal.fps,
                                     frame_times_seconds=signal.frame_times_seconds)
        self.assertEqual(signal.frames_read, 60)
        self.assertEqual(trace['sampleCount'], 59)
        self.assertEqual(trace['timingSource'], 'decoder')
        self.assertAlmostEqual(trace['points'][0]['timeSeconds'], 1 / 24, places=4)
        self.assertAlmostEqual(trace['points'][-1]['timeSeconds'], 58.5 / 12, places=4)

    def test_invalid_point_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            compact_motion_trace([0.1], 24, max_points=0)


if __name__ == "__main__":
    unittest.main()
