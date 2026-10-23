"""Training-loss tests verify sparse landmark targets are not pixel-averaged away."""

import unittest

import torch

from training.train_pose import _loss


class HeatmapLossTests(unittest.TestCase):
    def test_zero_heatmaps_have_unit_error_for_a_labeled_landmark(self):
        outputs = torch.zeros((1, 1, 2, 2))
        targets = torch.tensor([[[[1.0, 0.0], [0.0, 0.0]]]])
        weights = torch.tensor([[1.0]])

        loss = _loss(outputs, targets, weights, torch)

        self.assertEqual(float(loss.item()), 1.0)

    def test_unlabeled_keypoints_do_not_contribute_to_loss(self):
        outputs = torch.zeros((1, 2, 2, 2))
        targets = torch.ones_like(outputs)
        weights = torch.tensor([[1.0, 0.0]])

        loss = _loss(outputs, targets, weights, torch)

        self.assertEqual(float(loss.item()), 1.0)


if __name__ == "__main__":
    unittest.main()
