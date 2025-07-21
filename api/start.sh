#!/bin/bash
set -e

# Always run from the project root
cd "$(dirname "$0")/../.."

# Create venv if it doesn't exist
if [ ! -d "uwsbot/venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv uwsbot/venv
fi

# Activate venv
source uwsbot/venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r uwsbot/requirements.txt

# Start FastAPI app
exec uvicorn uwsbot.api.main:app --reload 