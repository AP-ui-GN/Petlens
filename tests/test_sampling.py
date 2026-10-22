"""Timestamp assembly and the long-clip note. No model and no committed video."""

import unittest

import numpy as np

from gait_engine.clip_quality import quality_notes
from gait_engine.sampling import _best_window, assemble_timestamps


class TimestampAssemblyTests(unittest.TestCase):
    def test_an_increasing_container_clock_is_kept_including_a_gap(self):
        stamps, source = assemble_timestamps([0.0, 0.033, 2.033], fps=30.0)
        self.assertEqual(source, "container")
        self.assertTrue(np.allclose(stamps, [0.0, 0.033, 2.033]))

    def test_a_backwards_reading_stays_missing_instead_of_an_index_estimate(self):
        stamps, source = assemble_timestamps([0.0, 0.05, 0.01, 0.15], fps=30.0)
        self.assertEqual(source, "container")
        self.assertTrue(np.isnan(stamps[2]))
        self.assertAlmostEqual(stamps[3], 0.15)

    def test_a_stuck_zero_clock_is_an_estimate_for_the_whole_file(self):
        stamps, source = assemble_timestamps([0.0, 0.0, 0.0, 0.0], fps=10.0)
        self.assertEqual(source, "frame-index-estimate")
        self.assertTrue(np.allclose(stamps, [0.0, 0.1, 0.2, 0.3]))

    def test_no_clock_at_all_is_unmeasured(self):
        stamps, source = assemble_timestamps([float("nan"), float("nan")], fps=0.0)
        self.assertEqual(source, "unmeasured")
        self.assertTrue(np.isnan(stamps).all())

    def test_a_time_gap_is_not_filled_with_zero_motion(self):
        timestamps = np.array([0.0, 0.05, np.nan, 3.0])
        motions = np.array([0.4, 0.5, 0.4])
        start, end = _best_window(timestamps, motions)
        self.assertEqual((start, end), (0.0, 3.0))
        # The pair that touches the missing timestamp is not a stillness sample.
        self.assertEqual(len(motions), len(timestamps) - 1)


class LongClipNoteTests(unittest.TestCase):
    def test_a_long_clip_does_not_claim_that_only_the_opening_is_measured(self):
        notes = quality_notes(
            frames_read=4000,
            fps=30.0,
            duration_seconds=150.0,
            width=640,
            height=480,
            brightness=0.4,
            motion_mean=0.05,
            motion_coverage=1.0,
        )
        self.assertEqual(len(notes), 1)
        self.assertNotIn("Only the opening is measured", notes[0])
        self.assertIn("busiest 20-second window", notes[0])
        self.assertIn("not automatically the opening", notes[0])


if __name__ == "__main__":
    unittest.main()
