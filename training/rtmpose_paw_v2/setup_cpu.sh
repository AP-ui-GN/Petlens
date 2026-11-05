#!/usr/bin/env bash
# No model/data downloads. Run from the repository root with uv 0.9.9 available.
set -euo pipefail
UV_BIN="${UV_BIN:-uv}"
PILOT_ENV="${PILOT_ENV:-tmp/rtmpose-paw-v2/.venv}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/petlens-rtmpose-uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/tmp/petlens-rtmpose-python}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/petlens-rtmpose-pip-cache}"
if [[ ! -x "$PILOT_ENV/bin/python" ]]; then
    "$UV_BIN" venv --python 3.10.16 --seed "$PILOT_ENV"
fi
"$PILOT_ENV/bin/python" -m pip install pip==24.0 setuptools==69.5.1 wheel==0.43.0 numpy==1.26.4
"$PILOT_ENV/bin/python" -m pip install --no-build-isolation -r training/rtmpose_paw_v2/requirements-cpu.lock.txt
"$PILOT_ENV/bin/python" -m pip check
