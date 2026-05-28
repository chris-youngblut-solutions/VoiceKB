# VoiceKB — hold-to-talk voice-to-text for the X1 Pro.
# Phase B prototype. No sudo, no system installs, no network after fetch-model.

set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := false

HF_HOME := justfile_directory() + "/models/hf"

default:
    @just --list

# One-time: create .venv and install pinned deps from pyproject.toml.
sync:
    uv sync

# One-time: pre-cache the medium.en model into ./models/ (~770 MB).
# Uses the shipped .venv; the model cache stays local to the project.
fetch-model: sync
    HF_HOME="{{HF_HOME}}" uv run python -m voicekb fetch-model

# Read-only sanity checks: python, audio, injection, network, model.
doctor: sync
    HF_HOME="{{HF_HOME}}" uv run python -m voicekb doctor

# Run the hold-to-talk daemon in the foreground. Ctrl-C to stop.
# Hotkey defaults to ctrl-shift-4; override with --hotkey turbo.
run *ARGS: sync
    HF_HOME="{{HF_HOME}}" uv run python -m voicekb run {{ARGS}}

# Benchmark RTF on a 10-second reference sample (recorded live).
bench: sync
    HF_HOME="{{HF_HOME}}" uv run python -m voicekb bench

# Delete .venv and cached models. Idempotent.
clean:
    rm -rf .venv models __pycache__
    find . -name '__pycache__' -type d -exec rm -rf {} +

# ---------------------------------------------------------------------
# Install the daemon as a user-scope systemd service + GNOME extension.
# All paths are user-local; no sudo anywhere in this target.
# ---------------------------------------------------------------------

EXT_UUID := "voicekb@ctyoungb.github.com"

install-user: sync fetch-model
    #!/usr/bin/env bash
    set -euo pipefail
    echo "[install] systemd --user unit"
    mkdir -p ~/.config/systemd/user
    sed 's|@VOICEKB_DIR@|{{justfile_directory()}}|g' \
        packaging/systemd/voicekb.service \
        > ~/.config/systemd/user/voicekb.service
    systemctl --user daemon-reload

    echo "[install] GSettings schema"
    mkdir -p ~/.local/share/glib-2.0/schemas
    cp packaging/gnome/schemas/com.github.ctyoungb.voicekb.gschema.xml \
       ~/.local/share/glib-2.0/schemas/
    glib-compile-schemas ~/.local/share/glib-2.0/schemas/

    echo "[install] GNOME Shell extension"
    mkdir -p ~/.local/share/gnome-shell/extensions
    rm -rf ~/.local/share/gnome-shell/extensions/{{EXT_UUID}}
    cp -r packaging/gnome/extension/{{EXT_UUID}} \
          ~/.local/share/gnome-shell/extensions/
    # Bundle the compiled schema inside the extension tree so Gio.Settings
    # can find it without requiring the system-level schema dir.
    mkdir -p ~/.local/share/gnome-shell/extensions/{{EXT_UUID}}/schemas
    cp packaging/gnome/schemas/com.github.ctyoungb.voicekb.gschema.xml \
       ~/.local/share/gnome-shell/extensions/{{EXT_UUID}}/schemas/
    glib-compile-schemas \
       ~/.local/share/gnome-shell/extensions/{{EXT_UUID}}/schemas/

    echo
    echo "[install] Done. Next steps:"
    echo "  1. Log out + log back in (GNOME Shell 49 Wayland can't reload)."
    echo "  2. gnome-extensions enable {{EXT_UUID}}"
    echo "  3. Open QuickSettings (top-right); VoiceKB toggle appears."
    echo
    echo "  To start now from CLI: systemctl --user start voicekb.service"

uninstall-user:
    #!/usr/bin/env bash
    set -euo pipefail
    systemctl --user stop voicekb.service 2>/dev/null || true
    systemctl --user disable voicekb.service 2>/dev/null || true
    rm -f ~/.config/systemd/user/voicekb.service
    systemctl --user daemon-reload
    gnome-extensions disable {{EXT_UUID}} 2>/dev/null || true
    rm -rf ~/.local/share/gnome-shell/extensions/{{EXT_UUID}}
    rm -f ~/.local/share/glib-2.0/schemas/com.github.ctyoungb.voicekb.gschema.xml
    glib-compile-schemas ~/.local/share/glib-2.0/schemas/ 2>/dev/null || true
    echo "[uninstall] Done. Log out/in to drop the extension from Shell."

# Tail the daemon log.
service-logs:
    journalctl --user -u voicekb.service -f

# Show daemon state.
service-status:
    systemctl --user status voicekb.service --no-pager || true
