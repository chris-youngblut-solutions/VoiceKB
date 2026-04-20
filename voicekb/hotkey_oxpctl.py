"""oxpctl D-Bus adapter — stub for Phase C.

Once oxpctl Phase 2 ships (see X1ProLinux/OnTheLift/oxpctl/DESIGN.md §14),
bind a `voice_trigger` event in /etc/oxpctl/config.yaml to a dummy exec
and subscribe to the InputEvent signal here. The signal carries
(event_name, metadata) per DESIGN §6 line 371.

Phase B runs on hotkey_evdev only. This file is a placeholder."""

from __future__ import annotations

from collections.abc import Callable


class OxpctlUnavailableError(RuntimeError):
    pass


def dispatch_hold_to_talk(
    chord_keys: tuple[str, ...],  # noqa: ARG001
    on_press: Callable[[], None],  # noqa: ARG001
    on_release: Callable[[], None],  # noqa: ARG001
) -> None:
    raise OxpctlUnavailableError(
        "oxpctl D-Bus dispatch is a Phase C feature and not wired up yet. "
        "Use the default evdev hotkey adapter."
    )
