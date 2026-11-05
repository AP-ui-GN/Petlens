#!/usr/bin/env bash
# Run from the PetLens repository root. No implicit model downloads.
set -euo pipefail
PILOT_PYTHON="${PILOT_PYTHON:-tmp/rtmpose-paw-v2/.venv/bin/python}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/petlens-mpl}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export MMPOSE_ROOT
MMPOSE_ROOT="$("$PILOT_PYTHON" -c 'from pathlib import Path; import mmpose; print(Path(mmpose.__file__).parent / ".mim")')"
case "${1:-check}" in
    check)
        unset PETLENS_ALLOW_RANDOM_INIT
        exec "$PILOT_PYTHON" -m training.rtmpose_paw_v2.preflight
        ;;
    smoke)
        unset PETLENS_AP10K_CHECKPOINT
        exec "$PILOT_PYTHON" -m training.rtmpose_paw_v2.preflight --allow-random-init --smoke
        ;;
    train)
        unset PETLENS_ALLOW_RANDOM_INIT
        : "${PETLENS_AP10K_CHECKPOINT:?Supply the exact original AP-10K .pth; see checkpoint-provenance.json}"
        "$PILOT_PYTHON" -c 'import torch; assert torch.cuda.is_available(), "Use a CUDA environment for the GPU pilot"'
        exec "$PILOT_PYTHON" "$MMPOSE_ROOT/tools/train.py" training/rtmpose_paw_v2/pilot_config.py
        ;;
    *)
        echo 'Usage: bash training/rtmpose_paw_v2/run.sh {check|smoke|train}' >&2
        exit 2
        ;;
esac
