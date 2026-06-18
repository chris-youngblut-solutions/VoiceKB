# VoiceKB

A user-scope CLI and GNOME Shell extension for hold-to-talk voice-to-text on Wayland: hold a hotkey, speak, release, and the transcript lands in whatever input is focused. No sudo daemon, no polkit, no Secure Boot changes, no network after the one-time model fetch. Audio is kept in RAM only, never written to disk.

Engine: CPU-only faster-whisper `medium.en` (int8). Tested on a OneXPlayer X1 Pro (Ryzen AI 9 HX 370), Fedora 43 / kernel 6.19.12, Wayland/GNOME; nothing in it is device-specific beyond that test coverage.

## What it does

- Captures 16 kHz mono audio to an in-memory ring buffer while the
  hotkey is held.
- On release, transcribes via faster-whisper `medium.en` (CPU int8).
- Injects text via `wtype` or `xdotool` (first that succeeds); if both
  fail, copies the transcript to the clipboard via `wl-copy` for a
  manual paste — a last-resort fallback, not a peer injector.
- Zeros the buffer. Logs only latency + token count to stderr.

Does not:

- Persist any audio or transcript to disk.
- Open any network socket after `fetch-model`.
- Run as root. Use sudo. Write outside this directory.
- Create system-level systemd units, udev rules, or polkit rules
  (`just install-user` creates a `systemd --user` unit only).

## Prereqs (check before first run)

Three user-level tools and one Fedora package. `just doctor` tells
you which are missing.

```bash
# 1. uv — Python env + dep resolver (user-level, no sudo)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. just — task runner (user-level via cargo, no sudo)
cargo install just
#   — or system-level if you prefer:
#   sudo dnf install just

# 3. Text injectors (install one or both; wl-clipboard is the fallback)
sudo dnf install wtype xdotool wl-clipboard
#   wtype    — native Wayland virtual-keyboard-v1 (blocked on Mutter/GNOME)
#   xdotool  — Xwayland clients (terminals, VS Code, older Electron)
#   wl-copy  — fallback: text lands on clipboard, hit Ctrl+V to paste

# 4. input group membership to read evdev keyboards (one-time)
sudo usermod -aG input "$USER" && newgrp input
```

Also verify you're on Wayland: `echo $XDG_SESSION_TYPE` should
print `wayland`.

Everything else (faster-whisper, sounddevice, evdev, numpy) is
pinned in `pyproject.toml` and installed into a project-local
`.venv/` by `just sync`.

## First run

```
just sync          # build .venv from pinned deps
just fetch-model   # pre-cache medium.en into ./models/ (~1.5 GB on disk)
just doctor        # read-only checks — tell you if anything's wrong
just run           # starts the hotkey listener; Ctrl-C to stop
```

## Using it

Default hotkey: **hold `Ctrl+Shift+4`**, speak, release. Text lands
in whatever input is focused.

Alt hotkeys:

```
just run --hotkey turbo        # hardware Turbo button (Ctrl+Alt+Meta)
just run --hotkey capslock     # single-key hold (CapsLock)
just run --hotkey ctrl-shift-semicolon
```

The `capslock` preset assumes CapsLock has been neutered at the XKB
layer so holding it doesn't toggle caps state:

```bash
gsettings set org.gnome.desktop.input-sources xkb-options "['caps:none']"
```

(evdev still sees the raw keycode, so the listener keeps working.)

## How it works

- `voicekb/capture.py` writes 16 kHz mono audio to a RAM-only ring
  buffer (`sounddevice`) while the hotkey is held; the buffer is zeroed
  on release.
- `voicekb/hotkey_evdev.py` is the user-mode evdev listener, with
  per-device state for phantom-event isolation; `voicekb/hotkey_oxpctl.py`
  is a call-compatible stub for a future device-daemon D-Bus adapter.
- `voicekb/transcribe.py` wraps faster-whisper `medium.en` (CPU int8).
- `voicekb/inject.py` is a tiered injector: `wtype` → `xdotool` →
  `wl-copy` fallback chain.
- `packaging/` carries the `systemd --user` unit (`Type=notify`,
  hardened) and the GNOME Shell 49 QuickToggle extension plus its
  GSettings schema; `voicekb/doctor.py` is the read-only diagnostic suite.

## Install as a background service (GNOME toggle)

Turn VoiceKB into a `systemd --user` service with a toggle in the
GNOME QuickSettings panel (the pill panel top-right, same row as
Wi-Fi and Bluetooth).

```bash
just install-user
# → copies voicekb.service to ~/.config/systemd/user/
# → installs com.github.ctyoungb.voicekb.gschema.xml
# → drops voicekb@ctyoungb.github.com under ~/.local/share/gnome-shell/extensions/

# Log out + log back in (GNOME Shell 49 on Wayland cannot reload live).
gnome-extensions enable voicekb@ctyoungb.github.com
```

Open the QuickSettings panel; click the VoiceKB toggle to start the
service. Subtitle shows `Warming…` during model load (multi-second
on CPU), then `Ready`. Use the hotkey as usual. Click again to stop.

Note: the service unit runs with `--hotkey capslock` (see the
CapsLock XKB note above); the foreground `just run` default is
`Ctrl+Shift+4`. Edit `packaging/systemd/voicekb.service` to change
the service hotkey.

Useful CLI:

```bash
just service-status          # systemctl --user status voicekb.service
just service-logs            # journalctl --user -u voicekb.service -f
systemctl --user start voicekb.service
systemctl --user stop voicekb.service
just uninstall-user          # clean removal of unit + schema + extension
```

### Known limits

- **Native-Wayland GNOME apps fall back to clipboard.** Firefox, Nautilus,
  GNOME Text Editor, and other apps that don't run under Xwayland can't
  accept injected keystrokes from `wtype` (Mutter refuses
  virtual-keyboard-v1 for unprivileged clients) or `xdotool` (X-only).
  VoiceKB copies the transcript to your clipboard and you press Ctrl+V.
  Xwayland clients (most terminals, VS Code, Electron apps) receive
  injection directly.
- **Each toggle-ON pays the model-load cost** (multi-second, CPU int8).
  The extension shows `Warming…` during this window. An always-up daemon
  with a GSettings-gated hotkey (lower latency, higher idle memory) is a
  named future upgrade; the GSettings schema is already shaped for it.

### Troubleshooting

- Toggle says `Error`: `just service-logs` for details. Common causes:
  `input` group membership missing, model cache not fetched, PipeWire
  source not visible.
- Toggle doesn't appear: re-run `gnome-extensions enable`, check
  `gnome-extensions info voicekb@ctyoungb.github.com`.
- First-utterance latency high: warm-up transcribes a 1-second silent
  clip during startup; if still slow, the model is likely loading from
  a cold cache (first run after `fetch-model`).

## Status

Version 0.1.0, SemVer (Decision 5). Python 3.12 (`>=3.12,<3.13`); deps
pinned in `pyproject.toml` (faster-whisper 1.0.3, sounddevice 0.4.7,
evdev 1.7.1, numpy `>=1.26,<2.2`).

Shipped: the evdev hotkey listener, RAM-only capture, faster-whisper
`medium.en` (CPU int8) transcription, the `wtype` → `xdotool` →
`wl-copy` tiered injector, the `systemd --user` unit, and the GNOME
Shell 49 QuickToggle extension.

Not in this release:

- An alternative hotkey adapter over a device-daemon D-Bus interface
  (call-compatible stub present at `voicekb/hotkey_oxpctl.py`).
- Upgrade toggle semantic from "service start/stop" to "GSettings-gated
  hotkey, daemon always up" for instant-resume (the schema is already
  shaped for it — additive change).
- Try Vulkan whisper.cpp on the Radeon 890M iGPU (unbenchmarked here; upstream reports large speedups).
- AT-SPI or xdg-desktop-portal RemoteDesktop path for native-Wayland
  injection (covers Firefox / GNOME Text Editor without clipboard).
- Revisit NPU path via FastFlowLM/Lemonade when Fedora hits
  kernel 7.0+.

## License

Apache-2.0 OR MIT dual (`LICENSE-APACHE`, `LICENSE-MIT`).
