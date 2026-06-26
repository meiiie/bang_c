#!/usr/bin/env bash
# HackAIthon 2026 - Bang C, Round 2 entry script.
# Reads the BTC-mounted test (/code/private_test.json) and writes
# submission.csv + submission_time.csv. Invoked by the image as:
#     CMD ["bash", "inference.sh"]
set -euo pipefail
cd "$(dirname "$0")"
exec python3 predict.py "$@"
