#!/usr/bin/env bash
# Run from extracted package root. Installs software only; no training.
set -euo pipefail
python training/rtmpose_paw_v2/colab/verify_package.py
mkdir -p outputs
python -c 'import sys,platform,json; print(json.dumps(dict(python=sys.version,platform=platform.platform()),indent=2))' > outputs/colab-host.txt
python -m pip show torch >> outputs/colab-host.txt 2>&1 || true
nvidia-smi >> outputs/colab-host.txt
# Keep Colab's notebook interpreter and preinstalled torch untouched.
python -m pip install --target /content/petlens-uv uv==0.9.9
UV=/content/petlens-uv/bin/uv
export UV_PYTHON_INSTALL_DIR=/content/petlens-python
export UV_CACHE_DIR=/content/petlens-uv-cache
"$UV" python install 3.10.16
"$UV" venv --python 3.10.16 --seed /content/petlens-env
PY=/content/petlens-env/bin/python
"$PY" -m pip install pip==24.0 setuptools==69.5.1 wheel==0.43.0 numpy==1.26.4
"$PY" -m pip install --no-build-isolation -r training/rtmpose_paw_v2/requirements-gpu.txt
"$PY" -m pip check
"$PY" -m pip freeze --all > outputs/colab-gpu.freeze.txt
bash training/rtmpose_paw_v2/colab/run.sh check
