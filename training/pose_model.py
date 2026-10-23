"""Small top-down heatmap model that consumes dog crops from the existing detector."""

from __future__ import annotations

import torch
from torch import nn
from torchvision.models import resnet18


class AP10KHeatmapModel(nn.Module):
    def __init__(self, keypoint_count: int = 17) -> None:
        super().__init__()
        backbone = resnet18(weights=None)
        self.backbone = nn.Sequential(*list(backbone.children())[:-2])
        self.upsampling_head = nn.Sequential(
            self._upsample_block(512, 256),
            self._upsample_block(256, 256),
            self._upsample_block(256, 256),
            nn.Conv2d(256, keypoint_count, kernel_size=1),
        )

    @staticmethod
    def _upsample_block(input_channels: int, output_channels: int) -> nn.Sequential:
        block = nn.Sequential(
            nn.ConvTranspose2d(
                input_channels,
                output_channels,
                kernel_size=4,
                stride=2,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(output_channels),
            nn.ReLU(inplace=True),
        )
        nn.init.normal_(block[0].weight, mean=0.0, std=0.001)
        return block

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.upsampling_head(self.backbone(images)))


def build_model() -> AP10KHeatmapModel:
    return AP10KHeatmapModel(keypoint_count=17)
