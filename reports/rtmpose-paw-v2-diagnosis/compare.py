import json
import os
from pathlib import Path
import numpy as np
from mmpose.apis import init_model, inference_topdown

root = Path("reports/rtmpose-paw-v2-diagnosis")
data = json.loads(Path("reports/rtmpose-paw-v2-experiment/temporal-diagnostic.coco.json").read_text())
images = {im["id"]: im for im in data["images"]}

base = "tmp/rtmpose-paw-v2/.venv/lib/python3.10/site-packages/mmpose/.mim"
original = "artifacts/petlens-colab-100step/models/rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206.pth"
os.environ["MMPOSE_ROOT"] = str(Path(base).resolve())
os.environ["PETLENS_AP10K_CHECKPOINT"] = str(Path(original).resolve())

models = {
    "original": (f"{base}/configs/animal_2d_keypoint/rtmpose/ap10k/rtmpose-m_8xb64-210e_ap10k-256x256.py", original),
    "trained": ("training/rtmpose_paw_v2/pilot_config.py", "artifacts/outputs/rtmpose-paw-v2-pilot/iter_100.pth"),
}
results = []

for name, (config, checkpoint) in models.items():
    model = init_model(config, checkpoint, device="cpu")
    for ann in data["annotations"]:
        image = images[ann["image_id"]]
        b = ann["bbox"]
        box = [[b[0], b[1], b[0]+b[2], b[1]+b[3]]]
        prediction = inference_topdown(model, "reports/paw-annotation-data-v1/" + image["file_name"], bboxes=box)[0].pred_instances.keypoints[0]
        gt = np.array(ann["keypoints"]).reshape(17, 3)
        for paw in (13, 16):
            if gt[paw, 2] > 0:
                results.append({
                    "model": name,
                    "frame": Path(image["file_name"]).name,
                    "paw": paw,
                    "error_px": round(float(np.linalg.norm(prediction[paw] - gt[paw, :2])), 2),
                    "label": gt[paw, :2].tolist(),
                    "prediction": prediction[paw].tolist()
                })
    print(name, "finished", flush=True)

(root / "paw-errors.json").write_text(json.dumps(results, indent=2))
for name in models:
    rows = sorted((r for r in results if r["model"] == name), key=lambda r: r["error_px"], reverse=True)
    print("\n", name.upper(), "mean error:", round(np.mean([r["error_px"] for r in rows]), 2))
    for r in rows[:3]:
        print(r["frame"], "paw", r["paw"], "error:", r["error_px"], "pixels")
print("\nSaved:", root / "paw-errors.json")
