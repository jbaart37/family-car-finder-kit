#!/usr/bin/env bash
# Starts the family page. Leave this terminal open while you're shopping; Ctrl+C stops it.
cd "$(dirname "$0")"
if [ ! -f config.json ]; then
  echo "No config.json yet. Run ./setup.sh first."
  exit 1
fi
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" car_agent.py serve --share
