#!/bin/sh
# Pack, restore or check SystemEarth's sample and the files derived from it.
# They are listed in data/PRIVATE_FILES.txt and kept out of git because the sample was
# shared for local work only. Pass the bundle between teammates privately; never commit it.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LIST="$ROOT/data/PRIVATE_FILES.txt"
PATHS=$(mktemp -t plotline-private.XXXXXX)
trap 'rm -f "$PATHS"' EXIT
grep -v -e '^#' -e '^$' "$LIST" > "$PATHS"

missing() {
  while read -r p; do [ -e "$ROOT/$p" ] || echo "$p"; done < "$PATHS"
}
absolute() {
  echo "$(CDPATH= cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"
}

case "${1:-}" in
  pack)
    [ $# -eq 2 ] || { echo "usage: $0 pack <bundle.tar.gz>" >&2; exit 2; }
    gaps=$(missing)
    [ -z "$gaps" ] || { printf 'error: missing private files:\n%s\n' "$gaps" >&2; exit 1; }
    out=$(absolute "$2")
    (cd "$ROOT" && tar -czf "$out" -T "$PATHS")
    echo "Packed $(wc -l < "$PATHS" | tr -d ' ') files into $out. Share it privately; never commit or upload it."
    ;;
  unpack)
    [ $# -eq 2 ] || { echo "usage: $0 unpack <bundle.tar.gz>" >&2; exit 2; }
    # Extract only the listed paths, so a bundle cannot write anywhere else in the checkout.
    tar -xzf "$(absolute "$2")" -C "$ROOT" -T "$PATHS"
    gaps=$(missing)
    [ -z "$gaps" ] || { printf 'error: the bundle lacks:\n%s\n' "$gaps" >&2; exit 1; }
    echo "Restored $(wc -l < "$PATHS" | tr -d ' ') private files."
    ;;
  check)
    gaps=$(missing)
    if [ -n "$gaps" ]; then
      echo "error: SystemEarth's sample data is not present (it is not in git)." >&2
      echo "Get the private bundle from a teammate, then run: scripts/private-data.sh unpack <bundle.tar.gz>" >&2
      exit 1
    fi
    echo "Private sample data present."
    ;;
  *)
    echo "usage: $0 pack|unpack <bundle.tar.gz> | check" >&2
    exit 2
    ;;
esac
