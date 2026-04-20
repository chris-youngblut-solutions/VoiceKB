from __future__ import annotations

import select
from collections import defaultdict
from collections.abc import Callable, Iterator

import evdev
from evdev import ecodes

_SELECT_TIMEOUT_S = 0.5


class HotkeyWatchError(RuntimeError):
    pass


def _keyboard_devices(chord_codes: set[int]) -> list[evdev.InputDevice]:
    devices: list[evdev.InputDevice] = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except PermissionError as exc:
            raise HotkeyWatchError(
                f"cannot open {path}: {exc}. Add $USER to the 'input' group: "
                "sudo usermod -aG input $USER && newgrp input"
            ) from exc
        except OSError:
            continue
        caps = set(dev.capabilities().get(ecodes.EV_KEY, []))
        is_keyboard = ecodes.KEY_A in caps and ecodes.KEY_LEFTCTRL in caps
        has_chord = chord_codes.issubset(caps)
        if is_keyboard and has_chord:
            devices.append(dev)
        else:
            dev.close()
    if not devices:
        raise HotkeyWatchError(
            "no evdev device emits the full chord; check keyboard wiring"
        )
    return devices


def watch(
    chord_keys: tuple[str, ...],
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[tuple[str, float]]:
    """Yield ('press', ts) when one device holds the full chord,
    ('release', ts) when that device releases any chord key. Non-
    exclusive read — we do not grab devices, so GNOME still sees
    events too. Per-device state isolates phantom events (LED-sync
    reflections, PS/2+USB duplication on laptop keyboards).

    If should_stop is provided, the loop polls it on every select()
    timeout and returns when it becomes truthy — lets daemons shut
    down cleanly on SIGTERM."""

    chord_codes = {getattr(ecodes, name) for name in chord_keys}
    devices = _keyboard_devices(chord_codes)
    fd_to_dev = {d.fd: d for d in devices}
    held: dict[int, set[int]] = defaultdict(set)
    chord_active = False
    stop = should_stop or (lambda: False)

    try:
        while not stop():
            rlist, _, _ = select.select(fd_to_dev, [], [], _SELECT_TIMEOUT_S)
            if not rlist:
                continue
            for fd in rlist:
                dev = fd_to_dev[fd]
                try:
                    events = list(dev.read())
                except OSError:
                    continue
                for event in events:
                    if event.type != ecodes.EV_KEY:
                        continue
                    code = event.code
                    if code not in chord_codes:
                        continue
                    if event.value == 1:
                        held[fd].add(code)
                    elif event.value == 0:
                        held[fd].discard(code)
                    now = event.timestamp()
                    any_complete = any(s >= chord_codes for s in held.values())
                    if any_complete and not chord_active:
                        chord_active = True
                        yield ("press", now)
                    elif chord_active and not any_complete:
                        chord_active = False
                        yield ("release", now)
    finally:
        for dev in devices:
            try:
                dev.close()
            except OSError:
                pass


def dispatch_hold_to_talk(
    chord_keys: tuple[str, ...],
    on_press: Callable[[], None],
    on_release: Callable[[], None],
    should_stop: Callable[[], bool] | None = None,
) -> None:
    """Block until should_stop() returns truthy (or forever if None).
    Calls on_press when any device first holds the full chord,
    on_release when no device holds it. Exceptions in callbacks
    propagate so the caller can surface them."""

    for event, _ts in watch(chord_keys, should_stop=should_stop):
        if event == "press":
            on_press()
        elif event == "release":
            on_release()
