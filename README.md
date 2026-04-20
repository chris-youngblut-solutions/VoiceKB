# VoiceKB — hold-to-talk voice-to-text for the X1 Pro

Local, hotkey-driven dictation with a GNOME toggle. Zero-risk to
device or data: no sudo daemon, no polkit, no Secure Boot changes,
no network after the one-time model fetch. Audio is kept in RAM
only, never written to disk.

Target: X1 Pro (Ryzen AI 9 HX 370), Fedora 43 / kernel 6.19.12,
Wayland. CPU-only faster-whisper `medium.en` (int8).

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
just fetch-model   # pre-cache medium.en into ./models/ (~770 MB)
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

(evdev still sees the raw keycode, so our listener keeps working.)

## What it does (and doesn't)

- Captures 16 kHz mono audio to an in-memory ring buffer while the
  hotkey is held.
- On release, transcribes via faster-whisper `medium.en` (CPU int8).
- Injects text via a tiered fallback: `wtype` → `xdotool` → `wl-copy`
  (clipboard + manual paste). The first tool that succeeds wins.
- Zeros the buffer. Logs only latency + token count to stderr.

Doesn't:

- Persist any audio or transcript to disk.
- Open any network socket after `fetch-model`.
- Run as root. Use sudo. Write outside this directory.
- Create systemd units, udev rules, or polkit rules.

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
  Deliberate simplicity tradeoff — the extension shows `Warming…` during
  this window. An always-up daemon with a GSettings-gated hotkey (lower
  latency, higher idle memory) is a named future upgrade; the GSettings
  schema is already shaped for it.

### Troubleshooting

- Toggle says `Error`: `just service-logs` for details. Common causes:
  `input` group membership missing, model cache not fetched, PipeWire
  source not visible.
- Toggle doesn't appear: re-run `gnome-extensions enable`, check
  `gnome-extensions info voicekb@ctyoungb.github.com`.
- First-utterance latency high: warm-up transcribes a 1-second silent
  clip during startup; if still slow, the model is likely loading from
  a cold cache (first run after `fetch-model`).

## Phase C (deferred forks, not in this release)

- Swap `hotkey_evdev` for `hotkey_oxpctl` once oxpctl Phase 2 D-Bus
  lands (stub already present).
- Upgrade toggle semantic from "service start/stop" to "GSettings-gated
  hotkey, daemon always up" for instant-resume (the schema is already
  shaped for it — additive change).
- Try Vulkan whisper.cpp on the Radeon 890M iGPU (2-12× faster).
- AT-SPI or xdg-desktop-portal RemoteDesktop path for native-Wayland
  injection (covers Firefox / GNOME Text Editor without clipboard).
- Revisit NPU path via FastFlowLM/Lemonade when Fedora hits
  kernel 7.0+.

See `../BulletinBoard/FastLane/voicekb-fastlane.md` for the premise
table and `../BulletinBoard/Decisions/` for dated decision logs.
