#!/usr/bin/env bash
# Family Car Finder setup for Mac/Linux: installs what it needs into .venv, then asks a few questions.
set -e
cd "$(dirname "$0")"

new_enough() { "$1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; }
# On a new Mac, /usr/bin/python3 is a placeholder that pops up an "install developer tools" window when run.
# Only try it if those tools are already installed.
usable() {
  local path
  path="$(command -v "$1" 2>/dev/null)" || return 1
  if [ "$path" = "/usr/bin/python3" ] && [ "$(uname)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
    return 1
  fi
}

# newest first, so an installed Python 3.12 wins even if "python3" still points at an older one
PY=""; OLD=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
  usable "$candidate" || continue
  if new_enough "$candidate"; then PY="$candidate"; break; fi
  [ -z "$OLD" ] && OLD="$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
done
if [ -z "$PY" ]; then
  if [ -n "$OLD" ]; then
    echo "Found Python $OLD, but Family Car Finder needs Python 3.10 or newer."
  else
    echo "Family Car Finder needs Python 3.10 or newer, and it isn't installed yet."
  fi
  echo "Install it from https://www.python.org/downloads/ (or run 'brew install python' if you use Homebrew), then run setup again."
  exit 1
fi
echo "Using $("$PY" -c 'import sys; print("Python %d.%d" % sys.version_info[:2])')"

if [ ! -x .venv/bin/python ]; then
  echo "Creating a private Python environment in .venv ..."
  "$PY" -m venv .venv
fi
echo "Installing dependencies (first time takes a minute) ..."
.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install --quiet -r requirements.txt

# python.org's Mac Python has no SSL certificates until its "Install Certificates" step is run; use certifi's bundle
export SSL_CERT_FILE="${SSL_CERT_FILE:-$(.venv/bin/python -m certifi)}"
.venv/bin/python setup.py
