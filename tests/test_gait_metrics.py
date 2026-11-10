"""Basic tests for PetLens gait measurements."""

import sys
import unittest

sys.path.insert(0, "src")

from petlens_gait.metrics import calculate_metrics


def prediction(index):
    return {
        "frameIndex": index,
        "timestampSeconds": index * 0.1,
        "keypoints": [
            {"name": "left_shoulder", "x": 100, "y": 40},
            {"name": "right_shoulder", "x": 100, "y": 60},
            {"name": "left_hip", "x": 0, "y": 40},
            {"name": "right_hip", "x": 0, "y": 60},
        ],
    }


def tracking(index, x, status="associated"):
    return {
        "frameIndex": index,
        "timestampSeconds": index * 0.1,
        "physicalTracks": [{
            "identity": 0,
            "status": status,
            "point": (
                {"x": x, "y": 100}
                if status == "associated" else None
            ),
        }],
    }


class GaitMetricsTests(unittest.TestCase):

    def test_stationary_paw(self):
        frames = [prediction(i) for i in range(3)]
        tracks = [tracking(i, 10) for i in range(3)]
        results = calculate_metrics(frames, tracks)

        self.assertEqual(len(results), 3)
        self.assertAlmostEqual(results[1]["speedPixelsPerSecond"], 0)
        self.assertAlmostEqual(results[2]["speedPixelsPerSecond"], 0)

    def test_moving_paw(self):
        frames = [prediction(i) for i in range(3)]
        tracks = [tracking(i, i * 10) for i in range(3)]
        results = calculate_metrics(frames, tracks)

        self.assertAlmostEqual(results[1]["speedPixelsPerSecond"], 100)
        self.assertAlmostEqual(results[2]["speedPixelsPerSecond"], 100)
        self.assertAlmostEqual(
            results[2]["normalizedBodyAxisPosition"], 0.2
        )

    def test_tracking_gap(self):
        frames = [prediction(i) for i in range(3)]
        tracks = [
            tracking(0, 0),
            tracking(1, 10, "unresolved"),
            tracking(2, 20),
        ]
        results = calculate_metrics(frames, tracks)

        self.assertEqual(len(results), 2)
        self.assertIsNone(results[-1]["speedPixelsPerSecond"])


if __name__ == "__main__":
    unittest.main()
