from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import evdev
import sounddevice as sd

from .config import Config

_OK = "[ OK ]"
_BAD = "[FAIL]"
_WARN = "[WARN]"


def _net_listeners_for_pid(pid: int) -> list[str]:
    try:
        result = subprocess.run(
            ["ss", "-tunap"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    lines: list[str] = []
    needle = f"pid={pid},"
    for line in result.stdout.splitlines():
        if needle in line:
            lines.append(line)
    return lines


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = _OK if ok else _BAD
    sep = " — " if detail else ""
    print(f"  {mark} {label}{sep}{detail}")
    return ok


def run(cfg: Config) -> int:
    print("VoiceKB doctor — read-only checks\n")
    failed = 0

    ok = sys.version_info[:2] == (3, 12)
    if not _check("Python 3.12", ok, f"found {sys.version.split()[0]}"):
        failed += 1

    session = os.environ.get("XDG_SESSION_TYPE", "")
    if not _check(
        "Wayland session", session == "wayland", f"XDG_SESSION_TYPE={session!r}"
    ):
        failed += 1

    wtype = shutil.which("wtype")
    xdotool = shutil.which("xdotool")
    wl_copy = shutil.which("wl-copy")
    injectors = [name for name, p in (("wtype", wtype), ("xdotool", xdotool)) if p]
    if not _check(
        "text injector on PATH",
        bool(injectors),
        ", ".join(injectors)
        if injectors
        else "install at least one: sudo dnf install wtype xdotool",
    ):
        failed += 1
    _check(
        "wl-copy fallback available",
        wl_copy is not None,
        wl_copy or "optional — sudo dnf install wl-clipboard",
    )

    try:
        sources = sd.query_devices(kind="input")
        has_input = sources is not None
    except Exception as exc:  # noqa: BLE001
        has_input = False
        sources = str(exc)
    _check(
        "PipeWire input device visible to sounddevice",
        has_input,
        f"{sources['name']!r}" if has_input else str(sources),
    )
    if not has_input:
        failed += 1

    try:
        devices = evdev.list_devices()
        kbd_count = 0
        for path in devices:
            try:
                dev = evdev.InputDevice(path)
            except PermissionError:
                kbd_count = -1
                break
            except OSError:
                continue
            caps = dev.capabilities().get(evdev.ecodes.EV_KEY, [])
            if evdev.ecodes.KEY_A in caps and evdev.ecodes.KEY_LEFTCTRL in caps:
                kbd_count += 1
            dev.close()
        if kbd_count == -1:
            _check(
                "evdev keyboards readable (input group)",
                False,
                "PermissionError — run: sudo usermod -aG input $USER && newgrp input",
            )
            failed += 1
        else:
            _check(
                "evdev keyboards readable (input group)",
                kbd_count > 0,
                f"{kbd_count} keyboard device(s)",
            )
            if kbd_count == 0:
                failed += 1
    except Exception as exc:  # noqa: BLE001
        _check("evdev keyboards readable", False, str(exc))
        failed += 1

    model_root = Path(cfg.model_dir)
    has_model = model_root.exists() and any(model_root.rglob("model.bin"))
    if not _check(
        "faster-whisper model cached in ./models/",
        has_model,
        f"{model_root}/" if has_model else "missing — run: just fetch-model",
    ):
        failed += 1

    # Own-process network listener sanity check.
    pid = os.getpid()
    listeners = _net_listeners_for_pid(pid)
    if not _check(
        "no network sockets for voicekb process",
        not listeners,
        "" if not listeners else "\n        ".join(listeners),
    ):
        failed += 1

    print()
    if failed:
        print(f"{_BAD} {failed} check(s) failed")
        return 1
    print(f"{_OK} all checks passed")
    return 0
