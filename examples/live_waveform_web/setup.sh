#!/usr/bin/env sh
set -eu
poetry install
poetry run python -c "import audio_io; print('audio-io example environment ready')"
printf '%s\n' "Run with: poetry run run-example --interface 0"
