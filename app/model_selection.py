"""Detect local graphics hardware and recommend a suitable Ollama chat model."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import threading
from copy import deepcopy


MODEL_OPTIONS = ("qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b")

_profile_lock = threading.Lock()
_profile: dict | None = None


def recommend_model(vram_mb: int | None) -> str:
    """Choose a conservative model size that fits the detected GPU memory."""

    if vram_mb is None or vram_mb < 4096:
        return "qwen2.5:1.5b"
    if vram_mb < 8192:
        return "qwen2.5:3b"
    return "qwen2.5:7b"


def _run(command: list[str]) -> str:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=4,
        check=False,
        creationflags=creationflags,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _detect_nvidia() -> tuple[str, int, str] | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    output = _run([
        executable,
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ])
    candidates = []
    for line in output.splitlines():
        try:
            name, memory = line.rsplit(",", 1)
            candidates.append((name.strip(), int(float(memory.strip())), "nvidia-smi"))
        except (TypeError, ValueError):
            continue
    return max(candidates, key=lambda item: item[1]) if candidates else None


def _detect_windows_gpu() -> tuple[str, int, str] | None:
    if platform.system() != "Windows":
        return None
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return None
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    )
    output = _run([powershell, "-NoProfile", "-NonInteractive", "-Command", script])
    if not output:
        return None
    try:
        rows = json.loads(output)
    except json.JSONDecodeError:
        return None
    if isinstance(rows, dict):
        rows = [rows]
    candidates = []
    for row in rows if isinstance(rows, list) else []:
        try:
            memory_mb = int(row.get("AdapterRAM") or 0) // (1024 * 1024)
        except (TypeError, ValueError):
            memory_mb = 0
        name = str(row.get("Name") or "GPU").strip()
        if memory_mb > 0:
            candidates.append((name, memory_mb, "windows-cim"))
    return max(candidates, key=lambda item: item[1]) if candidates else None


def detect_hardware_profile() -> dict:
    detected = _detect_nvidia() or _detect_windows_gpu()
    gpu_name, vram_mb, detector = detected if detected else (None, None, "cpu-fallback")
    selected = recommend_model(vram_mb)
    if gpu_name:
        reason = f"تم اكتشاف {gpu_name} بذاكرة رسومية تقارب {vram_mb} MB."
    else:
        reason = "لم تُكتشف ذاكرة GPU مخصصة؛ تم اختيار الموديل الأخف لضمان الاستقرار."
    return {
        "gpu_detected": bool(gpu_name),
        "gpu_name": gpu_name,
        "vram_mb": vram_mb,
        "detector": detector,
        "recommended_model": selected,
        "reason_ar": reason,
    }


def initialize_hardware_profile(force: bool = False) -> dict:
    global _profile
    with _profile_lock:
        if _profile is None or force:
            _profile = detect_hardware_profile()
        return deepcopy(_profile)


def hardware_profile() -> dict:
    return initialize_hardware_profile()
