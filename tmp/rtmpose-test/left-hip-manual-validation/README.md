# Manual left-hip validation

This separate experiment lets you mark the left hip on four original,
unannotated video frames. The browser interface does not load or display
RTMPose predictions.

## Start the marking page

From the PetLens workspace terminal, run:

```sh
.venv/pose312/bin/python tmp/rtmpose-test/left-hip-manual-validation/mark_left_hips.py --prepare
```

The script extracts frames 45, 55, 77, and 100 (preserving any existing
manual clicks), then starts a web server on port **8765**.

In VS Code / GitHub Codespaces:

1. Open the **Ports** tab in the bottom panel.
2. Choose **Forward a Port** and enter `8765`.
3. Use **Open in Browser** for the forwarded port.

The terminal also prints `http://localhost:8765/`; when working locally, open
that address directly. Keep the terminal running while you mark the frames.
Press **Ctrl+C** in the terminal to stop the server.

## Mark and correct points

The page shows all four clean frames. Click the dog's left hip on each image.
Clicking again replaces that frame's mark. **Clear mark** removes it if you
want to start over. Your click is saved immediately, so you can close and
reopen the page without losing completed marks.

Clicks are converted to coordinates in the original **426 × 240** frame,
with `(0, 0)` at the top-left, even when the browser scales the displayed
image. Manual coordinates are saved in
`manual-left-hip-marks.json`, separately from model predictions.

## Compare after marking

When you are satisfied with your marks, stop the server with **Ctrl+C**, then
run:

```sh
.venv/pose312/bin/python tmp/rtmpose-test/left-hip-manual-validation/compare_left_hip_marks.py
```

This separate script compares your marks with RTMPose's original predictions
and reports pixel distance, distance divided by torso length, and the raw
prediction score. The comparison results are saved to
`left-hip-comparison-results.json`. This reflects agreement with your manual
marks, not expert ground truth unless you have independently verified them.
