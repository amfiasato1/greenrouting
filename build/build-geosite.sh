#!/usr/bin/env bash
# Build a slim geosite.dat: overlay data/ onto upstream v2fly
# domain-list-community lists and run the upstream Go builder.
# Requires: go, $COMMUNITY_DIR checkout of v2fly/domain-list-community.
set -Eeuo pipefail

: "${COMMUNITY_DIR:=community}"

[[ -f "$COMMUNITY_DIR/go.mod" ]] || {
  echo "Error: $COMMUNITY_DIR is not a domain-list-community checkout" >&2
  exit 1
}

mkdir -p release
# Overlay our lists ON TOP of the upstream data directory: our category-ru
# resolves include: directives against upstream subcategory files, so the
# upstream data must stay intact.
cp -a ./data/. "$COMMUNITY_DIR/data/"
# Then drop everything the routing profiles do not reference, otherwise the
# builder would ship the whole upstream database (~1500 unused sections).
# The upstream category-ru (with its tld-ru blanket and all subcategories) is
# one of the roots, so it must survive pruning even though ./data has no such
# file anymore.
python3 build/prune-data.py "$COMMUNITY_DIR/data" $(basename -a ./data/*) category-ru

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
(cd "$COMMUNITY_DIR" && go run ./ -outputdir="$out")

test -s "$out/dlc.dat" || { echo "Error: builder produced no dlc.dat" >&2; exit 1; }
python3 build/filter-dat.py "$out/dlc.dat" release/geosite.dat PRIVATE CATEGORY-RU WHITELIST

# Every category the routing profiles reference must exist in the binary.
# The v2fly builder stores list names uppercased.
for section in PRIVATE CATEGORY-RU WHITELIST; do
  grep -aq "$section" release/geosite.dat ||
    { echo "Error: section $section missing from geosite.dat" >&2; exit 1; }
done
size=$(stat -c%s release/geosite.dat)
(( size < 20971520 )) || { echo "Error: geosite.dat is $size bytes, expected a slim build" >&2; exit 1; }
echo "geosite.dat: $size bytes"
