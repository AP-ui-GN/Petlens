"""Dog-only top-down crops and AP-10K heatmap targets."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path, PurePosixPath

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from gait_engine.ap10k_data import (
    DatasetValidationError,
    SCHEMA_VERSION,
    flip_ap10k_keypoints,
)
from gait_engine.pose_backend import AP10K_KEYPOINTS

_IMAGE_MEAN = np.asarray((0.485, 0.456, 0.406), dtype=np.float32)
_IMAGE_STD = np.asarray((0.229, 0.224, 0.225), dtype=np.float32)


class AP10KHeatmapDataset(Dataset):
    def __init__(
        self,
        annotations_path: Path,
        image_root: Path,
        *,
        species: str = "dog",
        input_size: tuple[int, int] = (192, 256),
        heatmap_size: tuple[int, int] = (48, 64),
        augment: bool = False,
        horizontal_flip_probability: float = 0.5,
        gaussian_sigma: float = 2.0,
    ) -> None:
        payload = json.loads(annotations_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise DatasetValidationError("Prepared split schema version is incompatible.")
        if payload.get("keypoints") != list(AP10K_KEYPOINTS):
            raise DatasetValidationError("Prepared split keypoint order is incompatible.")
        records = payload.get("records")
        if not isinstance(records, list):
            raise DatasetValidationError("Prepared split must contain a records list.")
        self.records = [
            record
            for record in records
            if isinstance(record, dict)
            and str(record.get("category_name", "")).casefold() == species.casefold()
        ]
        if not self.records:
            raise DatasetValidationError(
                f"Prepared split contains no instances for species {species!r}."
            )
        self.image_root = image_root.resolve()
        self.input_width, self.input_height = input_size
        self.heatmap_width, self.heatmap_height = heatmap_size
        self.augment = augment
        self.horizontal_flip_probability = horizontal_flip_probability
        self.gaussian_sigma = gaussian_sigma
        if min(*input_size, *heatmap_size) <= 0 or gaussian_sigma <= 0:
            raise ValueError("Image sizes and gaussian_sigma must be positive.")
        if not 0.0 <= horizontal_flip_probability <= 1.0:
            raise ValueError("horizontal_flip_probability must be between 0 and 1.")

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        record = self.records[index]
        relative_path = PurePosixPath(str(record["file_name"]))
        image_path = (self.image_root / Path(*relative_path.parts)).resolve()
        if not image_path.is_relative_to(self.image_root):
            raise DatasetValidationError("Image path escapes the configured image root.")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise DatasetValidationError(f"Image cannot be decoded: {record['file_name']!r}.")
        image_height, image_width = image.shape[:2]
        if (image_width, image_height) != (
            int(record["width"]),
            int(record["height"]),
        ):
            raise DatasetValidationError(
                f"Image dimensions changed after preparation: {record['file_name']!r}."
            )

        x, y, width, height = (float(value) for value in record["bbox_xywh"])
        left = max(0, math.floor(x))
        top = max(0, math.floor(y))
        right = min(image_width, math.ceil(x + width))
        bottom = min(image_height, math.ceil(y + height))
        if right <= left or bottom <= top:
            raise DatasetValidationError(f"Invalid dog crop for {record['file_name']!r}.")
        crop = image[top:bottom, left:right]
        crop = cv2.resize(
            crop,
            (self.input_width, self.input_height),
            interpolation=cv2.INTER_LINEAR,
        )
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        scale_x = self.input_width / (right - left)
        scale_y = self.input_height / (bottom - top)

        original_points = np.asarray(record["keypoints"], dtype=np.float32)
        points = original_points.copy()
        points[:, 0] = (points[:, 0] - left + 0.5) * scale_x - 0.5
        points[:, 1] = (points[:, 1] - top + 0.5) * scale_y - 0.5
        if self.augment and random.random() < self.horizontal_flip_probability:
            crop = cv2.flip(crop, 1)
            points = flip_ap10k_keypoints(points, self.input_width)

        heatmaps, weights = self._heatmaps(points)
        normalized = (crop.astype(np.float32) / 255.0 - _IMAGE_MEAN) / _IMAGE_STD
        image_tensor = torch.from_numpy(np.ascontiguousarray(normalized.transpose(2, 0, 1)))
        return (
            image_tensor,
            torch.from_numpy(heatmaps),
            torch.from_numpy(weights),
            torch.from_numpy(original_points),
            torch.tensor((left, top, right, bottom), dtype=torch.float32),
        )

    def _heatmaps(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        heatmaps = np.zeros(
            (len(AP10K_KEYPOINTS), self.heatmap_height, self.heatmap_width),
            dtype=np.float32,
        )
        weights = np.zeros((len(AP10K_KEYPOINTS),), dtype=np.float32)
        grid_y, grid_x = np.ogrid[: self.heatmap_height, : self.heatmap_width]
        variance = 2 * self.gaussian_sigma**2
        for index, (x, y, visibility) in enumerate(points):
            if visibility <= 0 or not (
                0 <= x < self.input_width and 0 <= y < self.input_height
            ):
                continue
            center_x = int(
                round((x + 0.5) * self.heatmap_width / self.input_width - 0.5)
            )
            center_y = int(
                round((y + 0.5) * self.heatmap_height / self.input_height - 0.5)
            )
            center_x = min(center_x, self.heatmap_width - 1)
            center_y = min(center_y, self.heatmap_height - 1)
            heatmaps[index] = np.exp(
                -((grid_x - center_x) ** 2 + (grid_y - center_y) ** 2) / variance
            )
            weights[index] = 1.0
        return heatmaps, weights
