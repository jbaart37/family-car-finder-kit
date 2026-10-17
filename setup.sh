#!/usr/bin/env bash
# Family Car Finder setup for Mac/Linux: installs what it needs into .venv, then asks a few questions.
set -e
cd "$(dirname "$0")"

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is needed and wasn't found. Install it from https://www.python.org/downloads/ and run ./setup.sh again."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating a private Python environment in .venv ..."
  "$PY" -m venv .venv
fi
echo "Installing dependencies (first time takes a minute) ..."
.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install --quiet -r requirements.txt

.venv/bin/python setup.py
