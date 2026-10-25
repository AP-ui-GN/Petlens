# PetLens validation graph exports

These are copies of the existing project validation report outputs. The source report is `reports/canine-pose-validation/`; the baseline comparison graphic is `reports/petlens-positive-results/01-validation-vs-baseline.png`.

The PCK results are from the experimental AP-10K dog-only **development validation** split: 470/1,104 visible keypoints (42.6%) for the pose model and 41/1,104 (3.7%) for the box-center baseline. The split selected the checkpoint and used ground-truth dog boxes. These values are not independent test evidence, end-to-end app accuracy, or walking-video/gait validation. The production app remains motion-only.

`06-confidence-distribution.png` and its SVG show uncalibrated peak heatmap scores, not probabilities of correctness. The accompanying `metrics.json` contains the graph data and evaluation protocol; `training.csv` contains the recorded training curve. Original SVG files are included for vector-quality inspection.
