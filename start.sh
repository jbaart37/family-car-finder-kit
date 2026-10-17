#!/usr/bin/env bash
# Starts the family page. Leave this window open while you're shopping; Ctrl+C stops it.
cd "$(dirname "$0")"
if [ ! -f config.json ]; then
  echo "No config.json yet. Run ./setup.sh first."
  exit 1
fi
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

# python.org's Mac Python has no SSL certificates until its "Install Certificates" step is run; use certifi's bundle
CERTS="$("$PY" -m certifi 2>/dev/null)"
[ -n "$CERTS" ] && export SSL_CERT_FILE="${SSL_CERT_FILE:-$CERTS}"

# On a Mac, stay awake while the family page is running (caffeinate is built into macOS).
# Closing a laptop's lid still puts it to sleep, so leave it open and plugged in.
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -i "$PY" car_agent.py serve --share
fi
exec "$PY" car_agent.py serve --share
