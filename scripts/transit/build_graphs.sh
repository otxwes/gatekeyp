#!/usr/bin/env bash
# scripts/transit/build_graphs.sh
#
# Build OpenTripPlanner (OTP 2.x) graphs for the transit-directions regions.
# Run on a build machine (e.g. the Mac), NOT on the Pi — graph builds need
# memory and CPU the Pi does not have to spare. Output goes to
# <build>/graphs/<id>/, which the private deploy runbook rsyncs to the server.
#
# Refresh cadence (also documented in the private runbook):
#   - GTFS feeds: monthly, or sooner when a feed changes shape/schema.
#   - OSM extracts: quarterly.
# Re-run this script for a refresh; then rsync + restart (runbook).
#
# No credentials are used: GTFS feeds and OSM metro extracts are public
# downloads. Feed URLs are verified and their attribution strings pinned
# before a region ships (design doc §12); registration-gated feeds are a
# rollout prerequisite.
#
# Written for macOS system bash (3.2): no associative arrays — region data
# lives in case statements instead. Attribution strings must stay in sync
# with DEFAULT_REGIONS in src/core/transit.py.
#
# Usage:
#   scripts/transit/build_graphs.sh <otp-jar> [region...]
#   <otp-jar>    path to otp-2.x.jar
#   region...    optional subset of: nyc la mtl (default: all)
#
# Environment knobs (mainly for testing/dry runs):
#   GATEKEYP_BUILD_DIR  override the build/output directory
#                       (default: <repo>/build; graphs land in $BUILD_DIR/graphs)
#   SKIP_DOWNLOAD=1     omit the curl steps (feeds must already exist in
#                       $BUILD_DIR/<region>/ as dummy or real files)
set -euo pipefail

# Region feed lists: GTFS zips (space-separated) + one OSM metro extract (PBF).
gtfs_urls() {
  case "$1" in
    nyc) echo "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mta_subway.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mta_bus.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_lirr.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mnr.zip" ;;
    la)  echo "https://gitlab.com/LACMTA/gtfs_disk/-/raw/main/gtfs_zero_public.zip https://open.mobilitydatabase.org/download/metrolink-ca-us" ;;
    mtl) echo "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip https://cdn.exo.quebec/exo_gtfs.zip https://rem.info/sites/default/files/gtfs/gtfs_rem.zip" ;;
  esac
}

osm_url() {
  case "$1" in
    nyc) echo "https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf" ;;
    la)  echo "https://download.geofabrik.de/north-america/us/california-latest.osm.pbf" ;;
    mtl) echo "https://extract.bbbike.org/osm/bbbike/mtl/mtl.osm.pbf" ;;
  esac
}

known_region() {
  case "$1" in
    nyc|la|mtl) return 0 ;;
    *) return 1 ;;
  esac
}

if [ $# -lt 1 ]; then
  echo "usage: build_graphs.sh <otp-jar> [region...]" >&2
  exit 2
fi
OTP_JAR="$1"
shift

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="${GATEKEYP_BUILD_DIR:-$ROOT/build}"
GRAPHS_DIR="$BUILD_DIR/graphs"
mkdir -p "$GRAPHS_DIR"

if [ $# -gt 0 ]; then
  for r in "$@"; do
    if ! known_region "$r"; then
      echo "unknown region: $r (available: nyc la mtl)" >&2
      exit 2
    fi
  done
  regions="$*"
else
  regions="nyc la mtl"
fi

for region in $regions; do
  echo "== region: $region =="
  dir="$BUILD_DIR/$region"
  mkdir -p "$dir"
  if [ "${SKIP_DOWNLOAD:-0}" != 1 ]; then
    for url in $(gtfs_urls "$region"); do
      out="$dir/$(basename "$url")"
      if [ -s "$out" ]; then
        echo "cached: $out"
      else
        echo "GET $url"
        curl -fSL --retry 3 -o "$out" "$url"
      fi
    done
    osm_out="$dir/$(basename "$(osm_url "$region")")"
    if [ ! -s "$osm_out" ]; then
      echo "GET $(osm_url "$region")"
      curl -fSL --retry 3 -o "$osm_out" "$(osm_url "$region")"
    fi
  else
    echo "SKIP_DOWNLOAD=1 — using cached inputs in $dir"
  fi

  # Build street+transit graph: OSM PBF must be the first base input.
  # OTP 2 --save writes graph.obj directly into the directory given,
  # so save straight into the final graphs/<id>/ staging directory.
  mkdir -p "$dir/inputs"
  java -Xms1G -Xmx3G -jar "$OTP_JAR" \
    --build "$dir/inputs" --save "$GRAPHS_DIR/$region" \
    --cache "$BUILD_DIR/.cache"

  echo "-- $region graph contents --"
  du -sh "$GRAPHS_DIR/$region"/* 2>/dev/null
  echo
done

echo "Done $(date +%Y%m%d). Graphs in $GRAPHS_DIR — next: rsync + restart (private runbook)."
