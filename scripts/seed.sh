#!/usr/bin/env bash
#
# Take a cold stack to a demo-ready system. One command, idempotent.
#
#   ./scripts/seed.sh
#
# This is the Phase 7 acceptance path:
#
#   docker compose down -v && docker compose up -d && ./scripts/seed.sh \
#     && ./scripts/smoke.sh
#
# Everything runs inside the api container rather than from the host venv, so
# it works on a machine that has Docker and nothing else. That is the point of
# the check: a teammate cloning the repo an hour before the demo should not
# also have to build a Python environment.
#
# Idempotent because each seeder owns a reserved phone block and clears exactly
# its own rows first. Landmarks are upserted on their natural key. Running this
# twice leaves the same system, not a doubled one.

set -euo pipefail

cd "$(dirname "$0")/.."

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'

DRIVERS="${SEED_DRIVERS:-12}"
PASSENGERS="${SEED_PASSENGERS:-5}"
RIDES="${SEED_RIDES:-20}"

step() { printf '\n%s=== %s ===%s\n' "$DIM" "$1" "$RESET"; }

in_api() { docker compose exec -T -e PYTHONPATH=/srv api "$@"; }

# ---------------------------------------------------------------- wait ----
# `docker compose up -d` returns as soon as the containers are started, not
# when Postgres is ready to take a connection. Seeding immediately is the most
# common way this sequence fails on a cold machine, and it fails with a
# connection error that looks like a configuration problem.
step "waiting for the stack"
for _ in $(seq 1 60); do
    if docker compose ps postgres --format '{{.Status}}' | grep -q healthy \
        && docker compose ps redis --format '{{.Status}}' | grep -q healthy; then
        printf '  postgres and redis are healthy\n'
        break
    fi
    sleep 2
done

if ! docker compose ps postgres --format '{{.Status}}' | grep -q healthy; then
    printf '%s  postgres never became healthy; check docker compose logs postgres%s\n' \
        "$RED" "$RESET"
    exit 1
fi

for _ in $(seq 1 60); do
    if docker compose ps api --format '{{.Status}}' | grep -q healthy; then
        printf '  api is healthy\n'
        break
    fi
    sleep 2
done

# ----------------------------------------------------------- migrate ----
step "schema"
in_api alembic upgrade head
printf '  at %s\n' "$(in_api alembic current 2>/dev/null | tail -1)"

# ---------------------------------------------------------- landmarks ----
# Bet 1 is the gazetteer, so an unseeded one is a demo with no first act.
step "landmarks"
in_api python scripts/seed_landmarks.py

# ------------------------------------------------------------- fleet ----
# The capability spread matters: Phase 6 matching is only demonstrable if some
# vehicles cannot serve some requests.
step "fleet"
in_api python scripts/seed_drivers.py --count "$DRIVERS"

# ----------------------------------------------------------- history ----
step "passengers and ride history"
in_api python scripts/seed_history.py --passengers "$PASSENGERS" --rides "$RIDES"

# ------------------------------------------------------------ report ----
step "what is now in the database"
docker compose exec -T postgres psql -U vora -d vora -tAc "
SELECT 'landmarks        ' || count(*) FROM landmarks
UNION ALL SELECT 'drivers online   ' || count(*) FROM drivers WHERE is_online
UNION ALL SELECT 'vehicles         ' || count(*) FROM vehicles
UNION ALL SELECT 'with a ramp      ' || count(*) FROM vehicles WHERE has_ramp
UNION ALL SELECT 'passengers       ' || count(*) FROM users WHERE role = 'passenger'
UNION ALL SELECT 'completed rides  ' || count(*) FROM rides WHERE status = 'completed'
" | sed 's/^/  /'

printf '\n%sseeded. run ./scripts/smoke.sh to verify the surface%s\n' "$GREEN" "$RESET"
