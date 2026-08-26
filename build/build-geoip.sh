#!/usr/bin/env bash
# Build a slim geoip.dat: take runetfreedom's full database (the only active
# maintainer of RU-relevant IP categories) and keep just the sections the
# routing profiles reference - PRIVATE plus the YANDEX ASN block.
set -Eeuo pipefail

: "${GEOIP_SOURCE:=https://github.com/runetfreedom/russia-v2ray-rules-dat/releases/latest/download/geoip.dat}"

mkdir -p release
src=$(mktemp)
trap 'rm -f "$src"' EXIT
curl -fsSL --retry 3 --retry-delay 2 "$GEOIP_SOURCE" -o "$src"
test -s "$src" || { echo "Error: empty geoip source" >&2; exit 1; }

python3 build/filter-dat.py "$src" release/geoip.dat PRIVATE YANDEX RU-WHITELIST
