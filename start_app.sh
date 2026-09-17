#!/usr/bin/env bash
# Cloudera AI Application entrypoint — always runs as a real Python process.
set -euo pipefail
cd "${CDSW_PROJECT:-$(dirname "$0")}"
exec python3 run_demo.py
