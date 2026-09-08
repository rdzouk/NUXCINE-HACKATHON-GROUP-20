#!/usr/bin/env bash
#
# The §8 demo script, as a rehearsal aid.
#
#   ./scripts/demo.sh          # walk the beats, timed
#   ./scripts/demo.sh --check  # verify the system is demo-ready, then stop
#
# This does not replace rehearsing. It is the backing track: it proves each
# beat works right now, on this box, and it times the whole thing so you know
# whether you are inside five minutes before you are standing in front of
# anybody.
#
# Run it twice. The first run tells you what is broken; the second tells you
# how long it takes when nothing is.

set -uo pipefail

cd "$(dirname "$0")/.."

BASE="${BASE:-http://localhost:8080/api/v1}"
PY=".venv/bin/python"

GREEN=$'\033[32m'; RED=$'\033[31m'; BOLD=$'\033[1m'; DIM=$'\033[2m'
RESET=$'\033[0m'

started=$(date +%s)
beat=0

say() {
    beat=$((beat + 1))
    printf '\n%s%d. %s%s\n' "$BOLD" "$beat" "$1" "$RESET"
    [ $# -gt 1 ] && printf '%s   "%s"%s\n' "$DIM" "$2" "$RESET"
}

elapsed() {
    local now
    now=$(date +%s)
    printf '%s   [%02d:%02d]%s\n' "$DIM" $(( (now - started) / 60 )) \
        $(( (now - started) % 60 )) "$RESET"
}

# ------------------------------------------------------- readiness ----
printf '%s%schecking the system is demo-ready%s\n' "$BOLD" "" "$RESET"

health=$(curl -sS "${BASE}/health" 2>/dev/null)
if [ -z "$health" ]; then
    printf '%s  the API is not answering. docker compose up -d%s\n' "$RED" "$RESET"
    exit 1
fi

overall=$(jq -r '.status' <<< "$health")
printf '  health: %s (osrm %s, db %s, redis %s)\n' \
    "$overall" \
    "$(jq -r '.components.osrm.status' <<< "$health")" \
    "$(jq -r '.components.database.status' <<< "$health")" \
    "$(jq -r '.components.redis.status' <<< "$health")"

counts=$(docker compose exec -T postgres psql -U vora -d vora -tAc "
SELECT count(*) FROM landmarks
UNION ALL SELECT count(*) FROM drivers WHERE is_online
UNION ALL SELECT count(*) FROM rides WHERE status = 'completed'" 2>/dev/null)
landmarks=$(sed -n 1p <<< "$counts")
online=$(sed -n 2p <<< "$counts")
history=$(sed -n 3p <<< "$counts")
printf '  seeded: %s landmarks, %s drivers online, %s rides of history\n' \
    "$landmarks" "$online" "$history"

ready=0
[ "${landmarks:-0}" -lt 100 ] && {
    printf '%s  the gazetteer is empty; Bet 1 has no first act. ./scripts/seed.sh%s\n' \
        "$RED" "$RESET"; ready=1; }
[ "${online:-0}" -lt 5 ] && {
    printf '%s  too few drivers online; matching will look broken. ./scripts/seed.sh%s\n' \
        "$RED" "$RESET"; ready=1; }
[ "${history:-0}" -lt 10 ] && {
    printf '%s  no ride history; the history screen demos nothing. ./scripts/seed.sh%s\n' \
        "$RED" "$RESET"; ready=1; }

if [ "$ready" -ne 0 ]; then
    exit 1
fi
printf '%s  ready%s\n' "$GREEN" "$RESET"

if [ "${1:-}" = "--check" ]; then
    exit 0
fi

# ----------------------------------------------------------- beats ----
say "The problem" \
    "Ask anyone in Yaounde for an address. They will name a carrefour."
curl -sS "${BASE}/places/search?q=warda" \
    | jq -c '.results[0] | {name, match_type, lat, lng}' | sed 's/^/   /'
printf '%s   and misspelled, words reversed:%s\n' "$DIM" "$RESET"
curl -sS "${BASE}/places/search?q=warda%20carefour" \
    | jq -c '.results[0] | {name, match_type}' | sed 's/^/   /'
elapsed

say "Book, match, track, and the PIN at pickup"
"$PY" scripts/ride_flow.py --base "$BASE" 2>&1 | tail -6 | sed 's/^/   /'
elapsed

say "Exactly one winner under concurrency" \
    "Twenty drivers accept the same ride at once."
"$PY" scripts/race_test.py --base "$BASE" -n 20 2>&1 | tail -4 | sed 's/^/   /'
elapsed

say "Trust economics, and the attacker inside our own incentives" \
    "A driver who accepts and idles earns nothing. The trace proves it."
"$PY" scripts/cancel_matrix.py --base "$BASE" 2>&1 | tail -4 | sed 's/^/   /'
elapsed

say "Safety: share the trip, hide the person"
"$PY" scripts/safety_smoke.py --base "$BASE" 2>&1 | tail -4 | sed 's/^/   /'
elapsed

say "Corridor" \
    "This is the transport model that already exists here."
"$PY" scripts/corridor_flow.py --base "$BASE" 2>&1 \
    | grep -E 'passenger |driver collects|corridor flow' | sed 's/^/   /'
elapsed

say "Accessibility, and why it is a legal requirement"
curl -sS "${BASE}/vehicles/capabilities" \
    | jq -r '.capabilities[] | "   \(.key): \(.description_fr)"'
printf '%s   No health data is stored. Law 2024/017 forbids it, so a trip\n' "$DIM"
printf '   records "needs a ramp", never anything about a person.%s\n' "$RESET"
elapsed

say "It survives the network you actually have"
"$PY" scripts/degradation_test.py --base "$BASE" 2>&1 | tail -3 | sed 's/^/   /'
elapsed

# --------------------------------------------------------- timing ----
total=$(( $(date +%s) - started ))
printf '\n=========================================\n'
printf 'total: %02d:%02d\n' $(( total / 60 )) $(( total % 60 ))
if [ "$total" -gt 300 ]; then
    printf '%sover five minutes. Cut from the bottom of §9, in order.%s\n' \
        "$RED" "$RESET"
else
    printf '%sinside five minutes%s\n' "$GREEN" "$RESET"
fi
