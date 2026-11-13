@echo off
echo === Installing elilain-player ===
python -m venv .venv
.venv\Scripts\activate
pip install -e .
echo Done. Run: python -m elilain_player
