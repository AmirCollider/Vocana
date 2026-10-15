#!/bin/sh
# Vocana for macOS and Linux: opens the studio in your browser.
# Needs Python 3.10+ (numpy and e2k are installed into Vocana's own folder
# the first time). Close this window, or press Ctrl+C, to quit.
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Vocana needs Python 3.10 or newer: https://www.python.org/downloads/"
  exit 1
fi
if ! "$PY" app/launch.py preflight >/dev/null 2>&1; then
  "$PY" app/launch.py ensure-deps --ask || exit 1
fi
exec "$PY" -X utf8 app/launch.py studio "$@"
