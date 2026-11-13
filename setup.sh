#!/bin/bash
set -e
echo "=== Installing elilain-player ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
echo "Done. Run: python -m elilain_player"
