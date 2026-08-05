#!/usr/bin/env bash
# One-command setup for the TDM calibration repo.
# Usage: ./setup.sh
set -euo pipefail

echo "== Initializing tdm submodule =="
git submodule update --init --recursive

if [ -f "tdm/VERSION" ]; then
	echo "== TDM version =="
	cat tdm/VERSION
fi

echo "== Current submodule commit =="
git submodule status

# --- Optional: environment setup ---
# Uncomment / adapt as needed for your TDM's environment.
#
# if [ -f "tdm/environment.yml" ]; then
#     conda env create -f tdm/environment.yml -n tdm-calibration || \
#     conda env update -f tdm/environment.yml -n tdm-calibration
# fi
#
# if [ -f "requirements.txt" ]; then
#     pip install -r requirements.txt
# fi

echo ""
echo "Setup complete. TDM submodule pinned at:"
git -C tdm log -1 --oneline
