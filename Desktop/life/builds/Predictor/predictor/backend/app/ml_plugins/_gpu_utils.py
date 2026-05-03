"""GPU detection helpers shared by ML plugins.

All functions degrade gracefully to CPU when CUDA, torch, or pynvml are
unavailable, so importing this module never fails on a CPU-only host.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from typing import Any


def cuda_visible_devices(default: str = "0") -> str:
    val = os.environ.get("PREDICTOR_CUDA_DEVICES")
    if val is not None:
        return val
    return os.environ.get("CUDA_VISIBLE_DEVICES", default)


def _torch_cuda_info() -> dict[str, Any] | None:
    try:
        import torch  # type: ignore
    except Exception:
        return None
    try:
        if not torch.cuda.is_available():
            return {"available": False}
        idx = 0
        name = torch.cuda.get_device_name(idx)
        try:
            props = torch.cuda.get_device_properties(idx)
            vram_gb = int(round(props.total_memory / (1024 ** 3)))
        except Exception:
            vram_gb = 0
        return {
            "available": True,
            "device": f"cuda:{idx}",
            "name": str(name),
            "vram_gb": vram_gb,
        }
    except Exception:
        return {"available": False}


def _nvidia_smi_info() -> dict[str, Any] | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode("utf-8").strip().splitlines()
        if not out:
            return None
        first = out[0]
        name, mem = (p.strip() for p in first.split(",", 1))
        return {
            "available": True,
            "device": "cuda:0",
            "name": name,
            "vram_gb": int(round(float(mem) / 1024.0)),
        }
    except Exception:
        return None


@lru_cache(maxsize=1)
def detect_gpu() -> dict[str, Any]:
    info = _torch_cuda_info()
    if info and info.get("available"):
        return info
    smi = _nvidia_smi_info()
    if smi:
        return smi
    return {"available": False, "device": "cpu", "name": "", "vram_gb": 0}


def get_lightgbm_device() -> str:
    return "gpu" if detect_gpu()["available"] else "cpu"


def get_xgboost_tree_method() -> str:
    return "gpu_hist" if detect_gpu()["available"] else "hist"


def get_torch_device():
    try:
        import torch  # type: ignore
    except Exception as exc:
        raise RuntimeError("torch is not installed; install requirements-gpu.txt") from exc
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
