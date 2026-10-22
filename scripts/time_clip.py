#!/usr/bin/env python3
"""Print per-stage seconds and peak RSS for one clip. Does not invent numbers."""

from __future__ import annotations

import sys
import time
from typing import Any, Callable

try:
    import resource as _resource
except ImportError:  # Windows does not provide the POSIX resource module.
    _resource = None
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def rss_mb() -> float | None:
    """Return peak RSS in MiB where the OS exposes it, otherwise None.

    Linux reports ru_maxrss in KiB; macOS reports bytes. Windows does not
    provide the POSIX resource module, so the benchmark still runs there but
    reports memory as unavailable.
    """
    if _resource is None:
        return None
    peak = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024.0 * 1024.0) if sys.platform == "darwin" else peak / 1024.0


def _supports_ap10k_gait(keypoint_schema: str) -> bool:
    """Gait formulas index AP-10K landmarks and must not run on COCO-17."""
    return keypoint_schema == "ap10k"


def time_pose_stages(backend: Any, frames: list[Any]) -> tuple[float | None, float, Any]:
    """Time weight load and the forward pass separately when a loader exists.

    ``model_load_seconds`` is None when the backend has no callable
    ``_ensure_loaded``. ``inference_seconds`` is always the wall time of
    ``process``. On the COCO backend, ``process`` calls ``_ensure_loaded``
    again; after this timer has already loaded, that second call returns
    immediately. When no loader is visible, a load inside ``process`` stays
    inside ``inference_seconds`` and is reported as not measured.
    """
    loader = getattr(backend, "_ensure_loaded", None)
    model_load_seconds: float | None = None
    if callable(loader):
        load_started = time.perf_counter()
        loader()
        model_load_seconds = time.perf_counter() - load_started
    infer_started = time.perf_counter()
    result = backend.process(frames)
    inference_seconds = time.perf_counter() - infer_started
    return model_load_seconds, inference_seconds, result


def time_gait_stage(result: Any, compute_gait_metrics: Callable[..., Any]) -> float | None:
    """Time AP-10K gait math, or return None for every other schema."""
    if not _supports_ap10k_gait(result.keypoint_schema):
        return None
    gait_started = time.perf_counter()
    compute_gait_metrics(
        result.keypoints,
        timestamps=result.timestamps_seconds,
        boxes=result.boxes,
        dog_frames_share=result.dog_frames_share,
    )
    return time.perf_counter() - gait_started


def format_seconds(label: str, seconds: float | None) -> str:
    """Format a timed stage. An unmeasured stage is never printed as zero."""
    if seconds is None:
        return f"{label} not_measured"
    return f"{label} {seconds:.3f}"


def format_peak_rss(peak_rss: float | None) -> str:
    """Format peak RSS. Unavailable memory is never printed as zero."""
    if peak_rss is None:
        return "peak_rss_mb not_available"
    return f"peak_rss_mb {peak_rss:.1f}"


def main() -> int:
    video = Path(sys.argv[1])
    from gait_engine.gait import compute_gait_metrics
    from gait_engine.pose_backend import get_pose_backend
    from gait_engine.sampling import sample_video

    started = time.perf_counter()
    sample_started = time.perf_counter()
    frames = sample_video(video)
    sample_seconds = time.perf_counter() - sample_started
    model_load_seconds, inference_seconds, result = time_pose_stages(
        get_pose_backend(), frames
    )
    gait_seconds = time_gait_stage(result, compute_gait_metrics)
    if gait_seconds is None:
        print(
            f"gait_metrics_skipped schema={result.keypoint_schema} requires=ap10k",
            file=sys.stderr,
        )
    if model_load_seconds is None:
        print(
            "model_load_seconds not_measured; inference_seconds is the whole process() call",
            file=sys.stderr,
        )
    total = time.perf_counter() - started
    pose_seconds = (
        inference_seconds
        if model_load_seconds is None
        else model_load_seconds + inference_seconds
    )
    print(f"frames {len(frames)}")
    print(f"sample_seconds {sample_seconds:.3f}")
    print(format_seconds("model_load_seconds", model_load_seconds))
    print(format_seconds("inference_seconds", inference_seconds))
    print(f"pose_seconds {pose_seconds:.3f}")
    print(format_seconds("gait_seconds", gait_seconds))
    print(f"total_seconds {total:.3f}")
    print(format_peak_rss(rss_mb()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
