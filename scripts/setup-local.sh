#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PLOTLINE_PYTHON:-python3.14}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: Python 3.14 is required; install it or set PLOTLINE_PYTHON to its executable." >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "error: Node.js and npm are required to install the local app dependencies." >&2
  exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PYTHON_VERSION" != "3.14" ]; then
  echo "error: Python 3.14 is required (found $PYTHON_VERSION at $PYTHON_BIN)." >&2
  exit 1
fi

if [ ! -x "$ROOT/.venv-data/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$ROOT/.venv-data"
fi
"$ROOT/.venv-data/bin/python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else "error: existing .venv-data must use Python 3.14; select a compatible environment before setup.")'
"$ROOT/.venv-data/bin/python" -m pip install -r "$ROOT/engine/requirements.txt"
npm ci --prefix "$ROOT/app"
echo "Local Python and app dependencies are ready. Run scripts/verify-local.sh from the repository root."
