#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
export PILOT_PYTHON=/content/petlens-env/bin/python
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export MPLCONFIGDIR=/tmp/petlens-mpl
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PETLENS_AP10K_CHECKPOINT="$PWD/models/rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206.pth"
unset PETLENS_ALLOW_RANDOM_INIT
export MMPOSE_ROOT
MMPOSE_ROOT="$("$PILOT_PYTHON" -c 'from pathlib import Path; import mmpose; print(Path(mmpose.__file__).parent / ".mim")')"
CONFIG=training/rtmpose_paw_v2/pilot_config.py
check() {
    "$PILOT_PYTHON" training/rtmpose_paw_v2/colab/verify_package.py
    "$PILOT_PYTHON" -m pip check
    "$PILOT_PYTHON" -m training.rtmpose_paw_v2.preflight --report-out outputs/checkpoint-preflight.json
    "$PILOT_PYTHON" training/rtmpose_paw_v2/colab/cuda_check.py
}
case "${1:-check}" in
    check) check ;;
    train)
        # A repeat launch is rejected to protect the first fixed pilot.
        test ! -d outputs/rtmpose-paw-v2-pilot || { echo 'Pilot output already exists; use a fresh extraction for a new run.' >&2; exit 1; }
        check
        mkdir -p outputs/evaluation
        "$PILOT_PYTHON" "$MMPOSE_ROOT/tools/test.py" "$CONFIG" "$PETLENS_AP10K_CHECKPOINT" --work-dir outputs/evaluation/baseline --out outputs/evaluation/baseline.json --dump outputs/evaluation/baseline.pkl
        bash training/rtmpose_paw_v2/run.sh train
        test -f outputs/rtmpose-paw-v2-pilot/iter_100.pth
        "$PILOT_PYTHON" "$MMPOSE_ROOT/tools/test.py" "$CONFIG" outputs/rtmpose-paw-v2-pilot/iter_100.pth --work-dir outputs/evaluation/candidate --out outputs/evaluation/candidate.json --dump outputs/evaluation/candidate.pkl
        "$PILOT_PYTHON" -m pip freeze --all > outputs/colab-gpu.freeze.txt
        cp PACKAGE_MANIFEST.json outputs/input-manifest.json
        cp -r training/rtmpose_paw_v2 outputs/training-source
        cp reports/rtmpose-paw-v2-experiment/{audit.json,checkpoint-provenance.json,cpu-preflight.json} outputs/
        tar -czf /content/petlens-pilot-results.tar.gz outputs
        sha256sum /content/petlens-pilot-results.tar.gz
        ;;
    *) echo 'Usage: bash training/rtmpose_paw_v2/colab/run.sh {check|train}' >&2; exit 2 ;;
esac
