#!/bin/bash
# Mac: double-click in Finder to run setup (macOS opens .command files in Terminal).
cd "$(dirname "$0")"
bash ./setup.sh
echo
read -r -p "Done. Press Return to close this window. "
