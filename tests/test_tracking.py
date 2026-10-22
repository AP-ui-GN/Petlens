"""Dog-box association with synthetic boxes. No model and no video."""

import unittest

from gait_engine.tracking import MIN_TRACK_IOU, associate_tracks


class TrackAssociationTests(unittest.TestCase):
    def test_no_dog_stays_empty(self):
        decisions = associate_tracks([[], []])
        self.assertEqual([item.state for item in decisions], ["no_dog", "no_dog"])
        self.assertTrue(all(item.box is None and item.segment_id is None for item in decisions))

    def test_one_dog_keeps_the_same_segment_when_the_boxes_overlap(self):
        first = (10.0, 10.0, 40.0, 40.0)
        moved = (18.0, 12.0, 40.0, 40.0)
        decisions = associate_tracks([[first], [moved]])
        self.assertEqual(decisions[0].state, "new_segment")
        self.assertEqual(decisions[0].box, first)
        self.assertEqual(decisions[1].state, "tracked")
        self.assertEqual(decisions[1].box, moved)
        self.assertEqual(decisions[0].segment_id, decisions[1].segment_id)
        self.assertGreaterEqual(MIN_TRACK_IOU, 0.1)

    def test_zero_overlap_does_not_switch_identity(self):
        first = (10.0, 10.0, 40.0, 40.0)
        other = (400.0, 10.0, 80.0, 80.0)
        decisions = associate_tracks([[first], [other]])
        self.assertEqual(decisions[1].state, "missing")
        self.assertIsNone(decisions[1].box)
        self.assertEqual(decisions[1].segment_id, decisions[0].segment_id)
        self.assertNotEqual(decisions[1].box, other)

    def test_a_short_gap_stays_missing_instead_of_copying_coordinates(self):
        first = (10.0, 10.0, 40.0, 40.0)
        later = (16.0, 12.0, 40.0, 40.0)
        decisions = associate_tracks([[first], [], [], [later]], max_continuous_gap=5)
        self.assertEqual(decisions[1].state, "missing")
        self.assertEqual(decisions[2].state, "missing")
        self.assertIsNone(decisions[1].box)
        self.assertIsNone(decisions[2].box)
        self.assertNotEqual(decisions[1].box, first)
        self.assertEqual(decisions[3].state, "tracked")
        self.assertEqual(decisions[3].box, later)
        self.assertEqual(decisions[3].segment_id, decisions[0].segment_id)

    def test_a_long_gap_starts_a_new_segment_even_when_the_box_overlaps(self):
        first = (10.0, 10.0, 40.0, 40.0)
        decisions = associate_tracks([[first], [], [], [first]], max_continuous_gap=2)
        self.assertEqual([item.state for item in decisions], ["new_segment", "missing", "missing", "new_segment"])
        self.assertIsNone(decisions[1].box)
        self.assertIsNone(decisions[2].box)
        self.assertEqual(decisions[3].box, first)
        self.assertNotEqual(decisions[3].segment_id, decisions[0].segment_id)

    def test_two_dogs_with_no_open_segment_are_ambiguous(self):
        decisions = associate_tracks([[(0.0, 0.0, 30.0, 30.0), (100.0, 0.0, 30.0, 30.0)]])
        self.assertEqual(decisions[0].state, "ambiguous")
        self.assertIsNone(decisions[0].box)
        self.assertIsNone(decisions[0].segment_id)

    def test_two_similar_overlaps_are_ambiguous_and_do_not_pick_a_box(self):
        previous = (0.0, 0.0, 100.0, 100.0)
        almost_same = (0.0, 0.0, 100.0, 100.0)
        shifted = (5.0, 0.0, 100.0, 100.0)
        decisions = associate_tracks([[previous], [almost_same, shifted]])
        self.assertEqual(decisions[1].state, "ambiguous")
        self.assertIsNone(decisions[1].box)
        self.assertEqual(decisions[1].segment_id, decisions[0].segment_id)

    def test_one_clear_overlap_keeps_that_dog_when_another_dog_is_far_away(self):
        previous = (0.0, 0.0, 40.0, 40.0)
        moved = (5.0, 0.0, 40.0, 40.0)
        far = (200.0, 0.0, 40.0, 40.0)
        decisions = associate_tracks([[previous], [far, moved]])
        self.assertEqual(decisions[1].state, "tracked")
        self.assertEqual(decisions[1].box, moved)

    def test_stable_ids_hold_across_several_overlapping_frames(self):
        boxes = [(10.0 + index, 10.0, 40.0, 40.0) for index in range(4)]
        decisions = associate_tracks([[box] for box in boxes])
        self.assertEqual(decisions[0].state, "new_segment")
        self.assertTrue(all(item.state == "tracked" for item in decisions[1:]))
        self.assertEqual({item.segment_id for item in decisions}, {decisions[0].segment_id})
        self.assertEqual([item.box for item in decisions], boxes)

    def test_reappearance_inside_the_gap_keeps_the_segment(self):
        first = (10.0, 10.0, 40.0, 40.0)
        back = (12.0, 11.0, 40.0, 40.0)
        decisions = associate_tracks([[first], [], [back]], max_continuous_gap=5)
        self.assertEqual(decisions[2].state, "tracked")
        self.assertEqual(decisions[2].box, back)
        self.assertEqual(decisions[2].segment_id, decisions[0].segment_id)

    def test_aging_turns_an_expired_empty_frame_into_no_dog(self):
        first = (10.0, 10.0, 40.0, 40.0)
        decisions = associate_tracks([[first], [], [], []], max_continuous_gap=2)
        self.assertEqual(
            [item.state for item in decisions],
            ["new_segment", "missing", "missing", "no_dog"],
        )
        self.assertTrue(all(item.box is None for item in decisions[1:]))
        self.assertIsNone(decisions[3].segment_id)

    def test_ambiguity_does_not_refresh_the_track_so_it_still_expires(self):
        first = (0.0, 0.0, 100.0, 100.0)
        twin_a = (0.0, 0.0, 100.0, 100.0)
        twin_b = (4.0, 0.0, 100.0, 100.0)
        later = (2.0, 0.0, 100.0, 100.0)
        decisions = associate_tracks(
            [[first], [twin_a, twin_b], [], [later]],
            max_continuous_gap=2,
        )
        self.assertEqual(decisions[1].state, "ambiguous")
        self.assertIsNone(decisions[1].box)
        self.assertEqual(decisions[2].state, "missing")
        self.assertEqual(decisions[3].state, "new_segment")
        self.assertNotEqual(decisions[3].segment_id, decisions[0].segment_id)

    def test_calls_do_not_share_segment_ids(self):
        box = (10.0, 10.0, 40.0, 40.0)
        first_job = associate_tracks([[box], [box], [box]])
        second_job = associate_tracks([[box]])
        self.assertEqual(second_job[0].segment_id, 1)
        self.assertEqual(second_job[0].segment_id, first_job[0].segment_id)
        self.assertEqual(second_job[0].state, "new_segment")


if __name__ == "__main__":
    unittest.main()
