#!/usr/bin/env bash
# ============================================================
#  Banff Auto-Booker — One-click setup (macOS / Linux)
#  Run:  bash setup.sh
# ============================================================
set -euo pipefail

echo
echo "==================================="
echo "  Banff Campsite Auto-Booker Setup"
echo "==================================="
echo

# -- Check Python 3 is available --
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info[:2])')
echo "Using $(python3 --version)"

echo "[1/4] Creating virtual environment..."
python3 -m venv venv

echo "[2/4] Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "[3/4] Installing dependencies..."
pip install -e ".[dev]"

echo "[4/4] Installing Playwright Chromium browser..."
playwright install chromium || echo "[WARN] Chromium install failed — retry later with: playwright install chromium"

# -- Copy config if not already present --
if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo
    echo "Created config.yaml from config.example.yaml."
    echo "→ Edit it now to set your campground and dates."
fi

echo
echo "==================================="
echo "  Setup complete!"
echo "==================================="
echo
echo "Next steps:"
echo "  1. Edit your config (if you haven't already):"
echo "       \${EDITOR:-nano} config.yaml"
echo
echo "  2. Activate the venv (if opening a new terminal):"
echo "       source venv/bin/activate"
echo
echo "  3. Run the booker:"
echo "       auto-booker"
echo
