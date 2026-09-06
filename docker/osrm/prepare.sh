#!/usr/bin/env bash
#
# Prepare the OSRM routing graph. Run once, in Phase 2, before enabling the
# `routing` compose profile.
#
# Deviation from §3, deliberate: this clips the Geofabrik Cameroon extract to a
# Yaounde and Douala bounding box before processing. osrm-extract on the whole
# country peaks in the low gigabytes, and this build shares a 5 GB WSL
# allocation with Postgres, Redis and the API. Clipping cuts the input roughly
# tenfold and costs nothing operationally: the service-area check already
# rejects anything outside the served region with 422.

set -euo pipefail

cd "$(dirname "$0")/../.."

DATA_DIR="osrm-data"
PBF_URL="https://download.geofabrik.de/africa/cameroon-latest.osm.pbf"
COUNTRY_PBF="${DATA_DIR}/cameroon-latest.osm.pbf"
REGION_PBF="${DATA_DIR}/region.osm.pbf"

# min_lng,min_lat,max_lng,max_lat covering Douala through Yaounde.
BBOX="${OSRM_BBOX:-9.55,3.60,11.75,4.20}"

OSRM_IMAGE="osrm/osrm-backend:latest"
OSMIUM_IMAGE="stadtnavi/osmium-tool:latest"

mkdir -p "$DATA_DIR"

if [ ! -f "$COUNTRY_PBF" ]; then
    echo "downloading the Cameroon extract (roughly 100 MB)"
    curl -fL --progress-bar -o "$COUNTRY_PBF" "$PBF_URL"
else
    echo "country extract already present, skipping download"
fi

if [ ! -f "$REGION_PBF" ]; then
    echo "clipping to ${BBOX}"
    docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "$OSMIUM_IMAGE" \
        osmium extract --bbox "$BBOX" --overwrite \
        -o /data/region.osm.pbf /data/cameroon-latest.osm.pbf
    ls -lh "$REGION_PBF"
else
    echo "clipped extract already present, skipping"
fi

echo "extracting the routing graph (car profile)"
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "$OSRM_IMAGE" \
    osrm-extract -p /opt/car.lua /data/region.osm.pbf

# MLD, not CH. Contraction hierarchies preprocess more slowly and this build
# has no need for the query speed difference at demo scale.
echo "partitioning"
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "$OSRM_IMAGE" \
    osrm-partition /data/region.osrm

echo "customising"
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "$OSRM_IMAGE" \
    osrm-customize /data/region.osrm

echo
echo "routing graph ready. Now:"
echo "  1. set OSRM_ENABLED=true in .env"
echo "  2. docker compose --profile routing up -d osrm"
echo "  3. docker compose restart api"
