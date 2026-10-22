"""Validation and canonicalization for the official AP-10K COCO annotations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .pose_backend import AP10K_KEYPOINTS

SCHEMA_VERSION = "petlens.ap10k-17.v1"
DATASET_URL = "https://github.com/AlexTheBad/AP-10K"
DATASET_LICENSE = "CC-BY-4.0"
GROUP_FIELDS = ("video_id", "individual_id", "dog_id", "source_id", "group_id")

_KEYPOINT_ALIASES = {
    "leye": "left_eye",
    "lefteye": "left_eye",
    "reye": "right_eye",
    "righteye": "right_eye",
    "nose": "nose",
    "neck": "neck",
    "rootoftail": "root_of_tail",
    "lshoulder": "left_shoulder",
    "leftshoulder": "left_shoulder",
    "lelbow": "left_elbow",
    "leftelbow": "left_elbow",
    "lfpaw": "left_front_paw",
    "leftfrontpaw": "left_front_paw",
    "rshoulder": "right_shoulder",
    "rightshoulder": "right_shoulder",
    "relbow": "right_elbow",
    "rightelbow": "right_elbow",
    "rfpaw": "right_front_paw",
    "rightfrontpaw": "right_front_paw",
    "lhip": "left_hip",
    "lefthip": "left_hip",
    "lknee": "left_knee",
    "leftknee": "left_knee",
    "lbpaw": "left_back_paw",
    "leftbackpaw": "left_back_paw",
    "rhip": "right_hip",
    "righthip": "right_hip",
    "rknee": "right_knee",
    "rightknee": "right_knee",
    "rbpaw": "right_back_paw",
    "rightbackpaw": "right_back_paw",
}


class DatasetValidationError(ValueError):
    """Raised when an AP-10K split cannot safely be used."""


def _normalize_keypoint_name(value: Any) -> str:
    compact = re.sub(r"[^a-z0-9]", "", str(value).lower())
    return _KEYPOINT_ALIASES.get(compact, compact)


def _finite_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError(f"{field} must be numeric.") from exc
    if not math.isfinite(number):
        raise DatasetValidationError(f"{field} must be finite.")
    return number


def _relative_image_path(file_name: Any) -> str:
    if not isinstance(file_name, str) or not file_name.strip():
        raise DatasetValidationError("image.file_name must be a non-empty string.")
    path = PurePosixPath(file_name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise DatasetValidationError(f"Unsafe image path: {file_name!r}")
    return path.as_posix()


def _identifier(value: Any, field: str) -> str | int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DatasetValidationError(f"{field} must be a string or integer.")
    return value


def _image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image:
        for chunk in iter(lambda: image.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _category_names(payload: dict[str, Any]) -> dict[str | int, str]:
    categories = payload.get("categories")
    if not isinstance(categories, list) or not categories:
        raise DatasetValidationError("categories must be a non-empty list.")
    matches: dict[str | int, str] = {}
    for category in categories:
        if not isinstance(category, dict):
            continue
        names = category.get("keypoints")
        if isinstance(names, list):
            normalized = [_normalize_keypoint_name(name) for name in names]
            if tuple(normalized) == AP10K_KEYPOINTS:
                category_id = _identifier(category.get("id"), "category.id")
                matches[category_id] = str(category.get("name", category_id))
    if not matches:
        raise DatasetValidationError(
            "No category declares the AP-10K 17-keypoint order; refusing to reinterpret channels."
        )
    return matches


def _validate_annotations(
    payload: dict[str, Any],
    split: str,
    image_root: Path,
    *,
    verify_images: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    if not isinstance(payload, dict):
        raise DatasetValidationError(f"{split}: annotation document must be an object.")
    category_names = _category_names(payload)
    images = payload.get("images")
    annotations = payload.get("annotations")
    if not isinstance(images, list) or not isinstance(annotations, list):
        raise DatasetValidationError(f"{split}: images and annotations must be lists.")

    image_by_id: dict[Any, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    groups: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for image in images:
        if not isinstance(image, dict) or "id" not in image:
            raise DatasetValidationError(f"{split}: each image needs an id.")
        image_id = _identifier(image["id"], f"{split} image.id")
        if image_id in image_by_id:
            raise DatasetValidationError(f"{split}: duplicate image id {image_id!r}.")
        width = _finite_number(image.get("width"), f"{split} image {image_id} width")
        height = _finite_number(image.get("height"), f"{split} image {image_id} height")
        if width <= 0 or height <= 0:
            raise DatasetValidationError(f"{split}: image dimensions must be positive.")
        file_name = _relative_image_path(image.get("file_name"))
        image_by_id[image_id] = image
        paths[str(image_id)] = file_name
        for group_field in GROUP_FIELDS:
            if image.get(group_field) is not None:
                groups[str(image_id)] = f"{group_field}:{image[group_field]}"
                break
        if verify_images:
            image_path = (image_root / Path(*PurePosixPath(file_name).parts)).resolve()
            if not image_path.is_relative_to(image_root.resolve()):
                raise DatasetValidationError(f"{split}: image path escapes the dataset root.")
            if not image_path.is_file():
                raise DatasetValidationError(f"{split}: missing image file {file_name!r}.")
            hashes[str(image_id)] = _image_sha256(image_path)

    canonical: list[dict[str, Any]] = []
    annotation_ids: set[Any] = set()
    for annotation in annotations:
        if not isinstance(annotation, dict):
            raise DatasetValidationError(f"{split}: each annotation must be an object.")
        image_id = _identifier(annotation.get("image_id"), f"{split} annotation.image_id")
        if image_id not in image_by_id:
            raise DatasetValidationError(
                f"{split}: annotation {annotation.get('id')!r} references an unknown image."
            )
        annotation_id = annotation.get("id")
        if annotation_id is not None:
            annotation_id = _identifier(annotation_id, f"{split} annotation.id")
            if annotation_id in annotation_ids:
                raise DatasetValidationError(f"{split}: duplicate annotation id {annotation_id!r}.")
            annotation_ids.add(annotation_id)
        category_id = _identifier(
            annotation.get("category_id"), f"{split} annotation.category_id"
        )
        if category_id not in category_names:
            raise DatasetValidationError(
                f"{split}: annotation {annotation_id!r} references a category "
                "without the AP-10K keypoint order."
            )
        image = image_by_id[image_id]
        width = float(image["width"])
        height = float(image["height"])
        bbox = annotation.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise DatasetValidationError(f"{split}: annotation bbox must be COCO xywh.")
        x, y, box_width, box_height = (
            _finite_number(value, f"{split} annotation bbox") for value in bbox
        )
        if box_width <= 0 or box_height <= 0 or x + box_width <= 0 or y + box_height <= 0:
            raise DatasetValidationError(f"{split}: annotation bbox must overlap the image.")
        keypoints = annotation.get("keypoints")
        if not isinstance(keypoints, list) or len(keypoints) != len(AP10K_KEYPOINTS) * 3:
            raise DatasetValidationError(
                f"{split}: annotation must contain exactly 17 (x, y, visibility) triplets."
            )
        points = []
        visible_count = 0
        for index, name in enumerate(AP10K_KEYPOINTS):
            point_x = _finite_number(keypoints[index * 3], f"{split} {name} x")
            point_y = _finite_number(keypoints[index * 3 + 1], f"{split} {name} y")
            visibility_value = _finite_number(keypoints[index * 3 + 2], f"{split} {name} visibility")
            if visibility_value not in (0.0, 1.0, 2.0):
                raise DatasetValidationError(f"{split}: {name} visibility must be 0, 1, or 2.")
            visibility = int(visibility_value)
            if visibility:
                visible_count += 1
                if not (0 <= point_x <= width and 0 <= point_y <= height):
                    raise DatasetValidationError(f"{split}: visible {name} is outside the image.")
            points.append([point_x, point_y, visibility])
        declared_count = annotation.get("num_keypoints")
        if declared_count is not None:
            declared_count_value = _finite_number(
                declared_count, f"{split} annotation num_keypoints"
            )
            if declared_count_value != visible_count:
                raise DatasetValidationError(
                    f"{split}: num_keypoints disagrees with visibility flags "
                    f"for annotation {annotation_id!r}."
                )
        canonical.append(
            {
                "image_id": image_id,
                "annotation_id": annotation_id,
                "file_name": paths[str(image_id)],
                "width": width,
                "height": height,
                "bbox_xywh": [x, y, box_width, box_height],
                "keypoints": points,
                "num_keypoints": visible_count,
                "group_key": groups.get(str(image_id)),
                "category_id": category_id,
                "category_name": category_names[category_id],
            }
        )
    if not canonical:
        raise DatasetValidationError(f"{split}: no annotated instances found.")
    return canonical, groups, hashes


def prepare_ap10k(
    dataset_root: Path,
    output_dir: Path,
    split_files: dict[str, Path],
    *,
    verify_images: bool = True,
) -> dict[str, Any]:
    """Validate official train/val/test splits and write a portable manifest."""

    required_splits = {"train", "val", "test"}
    if set(split_files) != required_splits:
        raise DatasetValidationError("Exactly the train, val, and test splits are required.")
    root = dataset_root.resolve()
    image_root = (root / "data").resolve()
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dataset": "AP-10K",
        "dataset_url": DATASET_URL,
        "dataset_license": DATASET_LICENSE,
        "keypoints": list(AP10K_KEYPOINTS),
        "split_provenance": "Official AP-10K split annotations; not randomly re-split.",
        "identity_grouping": "not available unless source images include identity/video metadata",
        "splits": {},
    }
    seen_image_ids: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    seen_groups: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    prepared_splits: dict[str, list[dict[str, Any]]] = {}
    split_source_names: dict[str, str] = {}

    for split in ("train", "val", "test"):
        source_path = Path(split_files[split]).resolve()
        if not source_path.is_file():
            raise DatasetValidationError(f"Missing {split} annotation file: {source_path}")
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"Invalid JSON in {source_path}: {exc}") from exc
        records, groups, hashes = _validate_annotations(
            payload, split, image_root, verify_images=verify_images
        )
        for record in records:
            image_id = str(record["image_id"])
            path_key = record["file_name"].casefold()
            for key, seen, label in (
                (image_id, seen_image_ids, "image id"),
                (path_key, seen_paths, "image path"),
            ):
                previous = seen.get(key)
                if previous is not None:
                    raise DatasetValidationError(
                        f"{label} {key!r} appears in both {previous} and {split}."
                    )
                seen[key] = split
        for image_id, group in groups.items():
            previous = seen_groups.get(group)
            if previous is not None and previous != split:
                raise DatasetValidationError(
                    f"Identity/source group {group!r} appears in both {previous} and {split}."
                )
            seen_groups[group] = split
        for image_id, digest in hashes.items():
            previous = seen_hashes.get(digest)
            if previous is not None and previous != split:
                raise DatasetValidationError(
                    f"Identical image content appears in both {previous} and {split}."
                )
            seen_hashes[digest] = split

        prepared_splits[split] = records
        split_source_names[split] = source_path.name

    output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        records = prepared_splits[split]
        split_path = output_dir / f"{split}.json"
        split_path.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "records": records}, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["splits"][split] = {
            "file": split_path.name,
            "annotation_count": len(records),
            "source_file": split_source_names[split],
        }

    if not seen_groups:
        manifest["identity_grouping"] = (
            "image-level official splits only; source files provide no supported identity/video "
            "group field, so same-dog leakage cannot be ruled out"
        )
    if verify_images and seen_hashes:
        manifest["duplicate_check"] = "SHA-256 identical files checked across official splits"
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
