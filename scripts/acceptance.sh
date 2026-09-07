#!/usr/bin/env bash
#
# Run every phase's acceptance check in order.
#
#   ./scripts/acceptance.sh                       # against the local stack
#   ./scripts/acceptance.sh https://host/api/v1   # against the deployment
#
# Exists so that "does the whole thing still work" is one command rather than
# six remembered ones. Each phase's checks stay runnable on their own; this
# just runs them all and reports which failed.
#
# Note that the geo evaluation and the ride harnesses need the local Docker
# stack even when pointed at a remote base URL, because they read the OTP out
# of the api container's logs and seed drivers directly in Postgres.

set -u

cd "$(dirname "$0")/.."

BASE="${1:-http://localhost:8080/api/v1}"
PY=".venv/bin/python"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'

failed=0
declare -a results=()

# Let the box settle between suites.
#
# Every login costs two argon2 hashes at 32 MiB, deliberately: a four-digit OTP
# is only safe because the hash is memory-hard. Ten suites back to back on a
# 5 GB box therefore queue behind each other, and a suite that would pass alone
# times out on the API's own fifteen-second limit. The failures move between
# runs, which is the signature of contention rather than a bug.
#
# The right fix at demo scale is to stop stacking the load, not to weaken the
# hash or lengthen the timeout.
SETTLE_S="${ACCEPTANCE_SETTLE_S:-12}"

# Deliberately no per-suite limit clearing here.
#
# It was added and then removed: every harness already calls reset_limits()
# inside its own login(), so clearing here cleared nothing that was not about
# to be cleared anyway, and each call is a `docker compose exec` that spawns a
# process inside the redis container. Fifteen of those, on a box already
# timing out quotes at fifteen seconds, made contention measurably worse.
#
# If a suite ever does fail on `otp_ip_hourly`, the cause is the shared
# localhost IP across a long session, and the fix is to let the box settle
# (ACCEPTANCE_SETTLE_S) rather than to add work to it.

run() {
    local label="$1"; shift
    printf '\n%s=== %s ===%s\n' "$DIM" "$label" "$RESET"
    if "$@"; then
        results+=("${GREEN}pass${RESET}  ${label}")
    else
        results+=("${RED}FAIL${RESET}  ${label}")
        failed=$((failed + 1))
    fi
    sleep "$SETTLE_S"
}

echo "VORA acceptance against ${BASE}"

run "phase 0  contract surface"  ./scripts/smoke.sh "$BASE"
run "phase 1  auth lifecycle"    "$PY" scripts/auth_smoke.py --base "$BASE"
run "phase 1  driver kyc gate"   "$PY" scripts/kyc_smoke.py --base "$BASE"
run "phase 2  gazetteer hit rate" "$PY" scripts/geo_eval.py --base "$BASE"
run "phase 2  fare quoting"      "$PY" scripts/quote_smoke.py --base "$BASE"
run "phase 3  ride lifecycle"    "$PY" scripts/ride_flow.py --base "$BASE"
run "phase 3  concurrent claim"  "$PY" scripts/race_test.py --base "$BASE" -n 20
run "phase 3  idor sweep"        "$PY" scripts/idor_sweep.py --base "$BASE"
run "phase 4  gps spoof filter"  "$PY" scripts/spoof_test.py --base "$BASE"
run "phase 4  live tracking"     "$PY" scripts/tracking_demo.py --base "$BASE"
run "phase 5  cancellation policy" "$PY" scripts/cancel_matrix.py --base "$BASE"
run "phase 5  share, sos, messages" "$PY" scripts/safety_smoke.py --base "$BASE"
run "phase 6  corridor rides"    "$PY" scripts/corridor_flow.py --base "$BASE"
run "phase 7  security audit"    ./scripts/security_audit.sh

# Last, and only against the local stack: it stops containers on purpose.
# Running it mid-suite would fail every suite after it for reasons that
# have nothing to do with those suites.
if [ "$BASE" = "http://localhost:8080/api/v1" ]; then
    run "phase 7  degradation drill" "$PY" scripts/degradation_test.py --base "$BASE"
fi

# The race test takes every driver offline so it can isolate its own race, so
# the demo fleet is restored here. Otherwise a fully passing suite leaves the
# system with no drivers online, which is exactly the state you do not want to
# discover ten minutes before a demo.
printf '\n%sre-seeding the demo fleet%s\n' "$DIM" "$RESET"
if docker compose exec -T -e PYTHONPATH=/srv api \
        python scripts/seed_drivers.py --count 10 >/dev/null 2>&1; then
    printf '  fleet restored\n'
else
    printf '  %scould not re-seed the fleet; run scripts/seed_drivers.py%s\n' \
        "$RED" "$RESET"
fi

printf '\n=========================================\n'
for line in "${results[@]}"; do
    printf '  %s\n' "$line"
done
printf '\n'

if [ "$failed" -gt 0 ]; then
    printf '%s%d suite(s) failed%s\n' "$RED" "$failed" "$RESET"
    exit 1
fi
printf '%severy acceptance check passed%s\n' "$GREEN" "$RESET"
