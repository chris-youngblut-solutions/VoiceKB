# VoiceKB

Hold-to-talk local voice-to-text dictation for Wayland on the X1 Pro.
Background `systemd --user` service + GNOME Shell QuickSettings toggle.

**Tier**: T1  **Language**: Python 3.12  **Test discipline**: pragmatic

## What this is

Speak-to-type that works anywhere a keyboard works, with a toggle in
the GNOME top-right panel. All local (no network after model fetch),
all user-scope (no sudo daemon, no root), all RAM-only for audio.
Engine: faster-whisper int8 `medium.en` on CPU. Injection: `wtype` →
`xdotool` → `wl-copy` fallback chain. Hotkey: evdev listener today,
oxpctl D-Bus stub for tomorrow.

## Build / test / lint

```sh
just                 # list all recipes
just sync            # build .venv from pinned deps
just fetch-model     # pre-cache medium.en (~770 MB) into ./models/
just doctor          # read-only sanity checks
just run             # foreground hotkey listener (terminal, Ctrl-C to stop)
just install-user    # install systemd --user service + GNOME extension
just uninstall-user  # remove both
just bench           # RTF measurement on a 10s live sample
just clean           # nuke .venv + models
```

## Architecture

- `voicekb/` — Python package. `__main__.py` is the CLI dispatcher.
- `voicekb/capture.py` — RAM-only ring buffer, `sounddevice`.
- `voicekb/transcribe.py` — faster-whisper wrapper.
- `voicekb/hotkey_evdev.py` — user-mode evdev listener (per-device
  state for phantom-event isolation).
- `voicekb/hotkey_oxpctl.py` — Phase C stub; D-Bus subscription to
  oxpctl's `InputEvent` signal once oxpctl Phase 2 ships.
- `voicekb/inject.py` — tiered injector (`wtype` → `xdotool` → `wl-copy`).
- `voicekb/doctor.py` — read-only diagnostic suite.
- `voicekb/sdnotify.py` — pure-stdlib `sd_notify()` for `Type=notify`.
- `voicekb/logging.py` — journald-friendly stderr logger.
- `packaging/systemd/voicekb.service` — user unit (`Type=notify`, hardened).
- `packaging/gnome/schemas/` — GSettings schema for extension state.
- `packaging/gnome/extension/voicekb@ctyoungb.github.com/` — GNOME Shell 49
  QuickToggle extension.

## Conventions

- Conventional Commits, signed (`git commit -sS`).
- Lockfile (`uv.lock`) committed.
- `pre-commit install` after clone.
- Ruff for lint + format. No other linter.
- GitHub Actions pinned by SHA.
- No `print()` in committed code — logger only.

## Hard constraints (inherited from Phase B)

- No sudo daemon, no root, no polkit, no Secure-Boot changes.
- No network after `just fetch-model`.
- No audio to disk — RAM ring buffer, zeroed on release.
- No systemd unit outside `~/.config/systemd/user/`.

## License

Apache-2.0 OR MIT dual (`LICENSE-APACHE`, `LICENSE-MIT`).

## See also

- `README.md` — what it is, install, tradeoffs.
