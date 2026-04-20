#!/usr/bin/env bash
# Pre-cache the faster-whisper model into ./models/.
# Invoked by `just fetch-model`. Idempotent — re-running is a no-op.

set -euo pipefail

cd "$(dirname "$0")/.."
export HF_HOME="${PWD}/models/hf"
exec uv run python -m voicekb fetch-model
