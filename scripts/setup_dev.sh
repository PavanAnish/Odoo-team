#!/usr/bin/env bash
# ==============================================================================
# Development Environment Setup Script for Odoo Subscription Management
# ==============================================================================

set -e

echo "=== Initializing Subscription Management Development Environment ==="

# 1. Check Python version
PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.10+ (or 3.9+)."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Detected Python version: $PY_VERSION"

# 2. Virtual Environment Setup
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists in $VENV_DIR."
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# 3. Upgrade pip and install requirements
echo "Installing project requirements..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# 4. Copy configuration template if local odoo.conf does not exist
if [ ! -f "config/odoo.conf" ]; then
    echo "Creating local config/odoo.conf from template..."
    cp config/odoo.conf.example config/odoo.conf
    echo "NOTE: Update config/odoo.conf with your local database credentials and Odoo core addons path."
else
    echo "config/odoo.conf already exists."
fi

# 5. Run module architecture validation
echo "Validating module manifests and XML/Python syntax..."
python3 scripts/validate_modules.py

echo "=== Development Environment Setup Completed Successfully! ==="
