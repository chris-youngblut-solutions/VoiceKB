"""oxpctl D-Bus adapter — placeholder.

Intended future path: bind a `voice_trigger` event in the device daemon's
config and subscribe to its InputEvent D-Bus signal here. Until that daemon
interface ships, the evdev adapter is the only hotkey backend.

The signature mirrors `hotkey_evdev.dispatch_hold_to_talk` exactly so the
adapter is call-compatible from `__main__` and fails with the intended
error, not a TypeError."""

from __future__ import annotations

from collections.abc import Callable


class OxpctlUnavailableError(RuntimeError):
    pass


def dispatch_hold_to_talk(
    chord_keys: tuple[str, ...],  # noqa: ARG001
    on_press: Callable[[], None],  # noqa: ARG001
    on_release: Callable[[], None],  # noqa: ARG001
    should_stop: Callable[[], bool] | None = None,  # noqa: ARG001
) -> None:
    raise OxpctlUnavailableError(
        "oxpctl D-Bus dispatch is not wired up yet. "
        "Use the default evdev hotkey adapter."
    )
