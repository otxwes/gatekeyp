#!/usr/bin/env bash
# scripts/transit/build_graphs.sh
#
# Build OpenTripPlanner (OTP 2.x) graphs for the transit-directions regions.
# Run on a build machine (e.g. the Mac), NOT on the Pi — graph builds need
# memory and CPU the Pi does not have to spare. Output goes to build/graphs/<id>/,
# which the private deploy runbook rsyncs to the server.
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
# Usage:
#   scripts/transit/build_graphs.sh <otp-jar> [region...]
#   <otp-jar>    path to otp-2.x.jar
#   region...    optional subset of: nyc la mtl (default: all)
set -euo pipefail

OTP_JAR="${1:?usage: build_graphs.sh <otp-jar> [region...]}"
shift
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$ROOT/build"
GRAPHS_DIR="$BUILD_DIR/graphs"
mkdir -p "$GRAPHS_DIR"

# Region feed list: GTFS zips + one OSM metro extract (PBF) per region.
# Attribution strings must match src/core/transit.py DEFAULT_REGIONS.
declare -A GTFS=(
  [nyc]="https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mta_subway.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mta_bus.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_lirr.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_mnr.zip"
  [la]="https://gitlab.com/LACMTA/gtfs_disk/-/raw/main/gtfs_zero_public.zip https://open.mobilitydatabase.org/download/metrolink-ca-us"
  [mtl]="https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip https://cdn.exo.quebec/exo_gtfs.zip https://rem.info/sites/default/files/gtfs/gtfs_rem.zip"
)
declare -A OSM=(
  [nyc]="https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf"
  [la]="https://download.geofabrik.de/north-america/us/california-latest.osm.pbf"
  [mtl]="https://extract.bbbike.org/osm/bbbike/mtl/mtl.osm.pbf"
)

feed() { # feed <region> <kind> — echo dest filename
  local region="$1" kind="$2" i=0 name
  for item in ${GTFS[$region]:-}; do
    i=$((i + 1))
    [ "$kind" = "gtfs-$i" ] && basename "$item" && return 0
  done
  return 1
}

fetch_day() { date +%Y%m%d; }

for region in "${@:-nyc la mtl}"; do
  echo "== region: $region =="
  dir="$BUILD_DIR/$region"
  mkdir -p "$dir/build"
  for url in ${GTFS[$region]}; do
    out="$dir/$(basename "$url")"
    [ -s "$out" ] && { echo "cached: $out"; continue; }
    echo "GET $url"
    curl -fSL --retry 3 -o "$out" "$url"
  done
  osm_url="${OSM[$region]}"
  osm_out="$dir/$(basename "$osm_url")"
  [ -s "$osm_out" ] || { echo "GET $osm_url"; curl -fSL --retry 3 -o "$osm_out" "$osm_url"; }

  # Build street+transit graph: OSM PBF must be the first base input.
  java -Xms1G -Xmx3G -jar "$OTP_JAR" \
    --build --save "$dir" \
    --cache "$BUILD_DIR/.cache"
  cp -R "$dir/build" "$GRAPHS_DIR/$region"
  rm -rf "$dir/build"

  echo "-- $region graph contents --"
  du -sh "$GRAPHS_DIR/$region"/*
  echo
done

echo "Done $(fetch_day). Graphs in $GRAPHS_DIR — next: rsync + restart (private runbook)."
