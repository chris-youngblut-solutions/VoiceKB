from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class InjectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Tool:
    name: str
    path: str | None
    argv: tuple[str, ...]


def _available_tools() -> list[_Tool]:
    tools: list[_Tool] = []
    wtype = shutil.which("wtype")
    if wtype:
        tools.append(_Tool("wtype", wtype, (wtype, "--")))
    xdotool = shutil.which("xdotool")
    if xdotool:
        tools.append(
            _Tool(
                "xdotool",
                xdotool,
                (xdotool, "type", "--clearmodifiers", "--delay", "1", "--"),
            )
        )
    return tools


def _try_tool(tool: _Tool, text: str) -> tuple[bool, str]:
    result = subprocess.run(
        [*tool.argv, text],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, ""
    stderr = result.stderr.strip() or f"exit {result.returncode}"
    return False, stderr


def _maybe_copy_to_clipboard(text: str) -> bool:
    wl_copy = shutil.which("wl-copy")
    if wl_copy is None:
        return False
    result = subprocess.run(
        [wl_copy],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def inject(text: str) -> None:
    if not text:
        return
    tools = _available_tools()
    if not tools:
        raise InjectionError(
            "no injector found — install at least one: "
            "sudo dnf install wtype xdotool"
        )
    errors: list[str] = []
    for tool in tools:
        ok, err = _try_tool(tool, text)
        if ok:
            return
        errors.append(f"{tool.name}: {err}")
    detail = "; ".join(errors)
    copied = _maybe_copy_to_clipboard(text)
    hint = " — text copied to clipboard, press Ctrl+V to paste" if copied else ""
    raise InjectionError(f"all injectors failed ({detail}){hint}")
