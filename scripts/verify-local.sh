#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv-data/bin/python"
STORE="$ROOT/artifacts/stores/exp-0109a8d6c4782217871315b92c63a971d11ebd164585c80981f24c55b4f68fea/separate_zstd_l19"

if [ ! -x "$PYTHON" ]; then
  echo "error: local Python environment is missing; run scripts/setup-local.sh first." >&2
  exit 1
fi
if [ ! -d "$ROOT/app/node_modules" ]; then
  echo "error: app dependencies are missing; run scripts/setup-local.sh first." >&2
  exit 1
fi

cd "$ROOT"
"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 14), f"Python 3.14 required, found {sys.version.split()[0]}"'
"$PYTHON" -B -m engine.verify
"$PYTHON" -B -m engine.jrc --verify artifacts/jrc-baseline-v1.json
"$PYTHON" -B -m engine --plot P-0003 --store "$STORE" >/dev/null
echo "P-0003 Hansen full query: source and compact results match."
"$PYTHON" -B -m engine --plot P-0003 --access indexed --store "$STORE" >/dev/null
echo "P-0003 Hansen indexed query: source and compact results match."
npm run build --prefix app
