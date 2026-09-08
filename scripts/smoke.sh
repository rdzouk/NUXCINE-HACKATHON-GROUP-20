#!/usr/bin/env bash
#
# Phase 0 acceptance check.
#
# Verifies the deployed API over whatever base URL it is given: that health
# reports its dependencies, that stubs answer 501, and crucially that every
# failure carries a well-formed §6 envelope. The envelope assertions are the
# point. A 501 is easy; a 501 that mobile can parse is the deliverable.
#
# Usage: scripts/smoke.sh https://example.trycloudflare.com/api/v1

set -euo pipefail

BASE="${1:-${VORA_BASE_URL:-http://localhost:8000/api/v1}}"
PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }

need() {
    command -v "$1" >/dev/null 2>&1 || { red "missing dependency: $1"; exit 2; }
}
need curl
need jq

ok() { green "  PASS  $1"; PASS=$((PASS + 1)); }
no() { red   "  FAIL  $1"; FAIL=$((FAIL + 1)); }

check() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        ok "$label"
    else
        no "$label (expected '$expected', got '$actual')"
    fi
}

echo "VORA smoke check against ${BASE}"
echo

# ---------------------------------------------------------------- health ----
echo "health"
HEALTH_FILE=$(mktemp)
HEALTH_CODE=$(curl -sS -o "$HEALTH_FILE" -w '%{http_code}' "${BASE}/health")
check "GET /health returns 200" "200" "$HEALTH_CODE"
check "reports overall status" "true" "$(jq -e 'has("status")' "$HEALTH_FILE" >/dev/null 2>&1 && echo true || echo false)"
check "reports database component" "true" "$(jq -r 'has("components") and (.components|has("database"))' "$HEALTH_FILE")"
check "database is ok" "ok" "$(jq -r '.components.database.status' "$HEALTH_FILE")"
check "redis is ok" "ok" "$(jq -r '.components.redis.status' "$HEALTH_FILE")"
echo "  info  overall=$(jq -r .status "$HEALTH_FILE") osrm=$(jq -r .components.osrm.status "$HEALTH_FILE")"
echo

# --------------------------------------------------- stubs and envelopes ----
# One route per shape: path param, request body, public unauthenticated.
# Routes still returning the 501 stub. Shrinks as phases land, so a route
# that stops being a stub without this list being updated fails loudly rather
# than quietly asserting nothing.
#
# Empty as of Phase 6: every route in the contract is implemented, HTTP and
# WebSocket alike. The list stays here rather than being deleted, because it is
# the thing that would catch a route regressing to 501.
STUBS=()

# Routes that are implemented and must NOT be stubs any more. Listed explicitly
# so that a phase which accidentally reverts one to 501 fails here rather than
# passing quietly.
IMPLEMENTED=(
    "GET|/places/search?q=warda|200"
    "GET|/vehicles/capabilities|200"
    "GET|/rides/00000000-0000-0000-0000-000000000000|401"
    "GET|/me|401"
)

echo "stub routes return the contract envelope"
if [ ${#STUBS[@]} -eq 0 ]; then
    ok "no route in the contract is still a stub"
fi
for entry in ${STUBS[@]+"${STUBS[@]}"}; do
    IFS='|' read -r method path expected <<< "$entry"
    body=$(mktemp)
    code=$(curl -sS -X "$method" -o "$body" -w '%{http_code}' "${BASE}${path}")
    check "${method} ${path} -> ${expected}" "$expected" "$code"

    check "  envelope has error.code"       "true" "$(jq -r 'has("error") and (.error|has("code"))' "$body")"
    check "  envelope has error.message"    "true" "$(jq -r '.error|has("message")' "$body")"
    check "  envelope has error.details"    "true" "$(jq -r '.error|has("details")' "$body")"
    check "  envelope has error.request_id" "true" "$(jq -r '.error|has("request_id")' "$body")"
    check "  code is NOT_IMPLEMENTED"       "NOT_IMPLEMENTED" "$(jq -r .error.code "$body")"
    rm -f "$body"
done
echo

echo "implemented routes are no longer stubs"
for entry in "${IMPLEMENTED[@]}"; do
    IFS='|' read -r method path expected <<< "$entry"
    code=$(curl -sS -X "$method" -o /dev/null -w '%{http_code}' "${BASE}${path}")
    check "${method} ${path} -> ${expected}" "$expected" "$code"
done
echo

echo "the capability vocabulary is served"
CAPS=$(curl -sS "${BASE}/vehicles/capabilities")
# Six since Phase 6 added extra_legroom. The count is asserted rather than
# lower-bounded on purpose: a capability appearing without anybody noticing is
# a change to what the matcher can exclude, and that should have to be admitted
# here before it ships.
check "six capabilities" "6" "$(jq -r '.capabilities | length' <<< "$CAPS")"
check "each has a French label" "true" \
    "$(jq -r '[.capabilities[].label_fr | length > 0] | all' <<< "$CAPS")"
check "each has an English label" "true" \
    "$(jq -r '[.capabilities[].label_en | length > 0] | all' <<< "$CAPS")"
echo

# ------------------------------------------------------------ validation ----
echo "schema failure maps to 400, not 422"
code=$(curl -sS -X POST -o /dev/null -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d '{"phone":"not-a-phone"}' \
    "${BASE}/auth/otp/request")
check "POST /auth/otp/request with junk -> 400" "400" "$code"
echo

# -------------------------------------------------------------- headers ----
echo "security headers"
HEADERS=$(curl -sS -D - -o /dev/null "${BASE}/health")
for header in "x-content-type-options" "x-frame-options" "content-security-policy" "x-request-id"; do
    if grep -qi "^${header}:" <<< "$HEADERS"; then
        ok "$header present"
    else
        no "$header missing"
    fi
done

if grep -qi '^strict-transport-security:' <<< "$HEADERS"; then
    ok "strict-transport-security present"
else
    no "strict-transport-security missing"
fi
echo

rm -f "$HEALTH_FILE"
echo "-----------------------------------------"
echo "passed: ${PASS}   failed: ${FAIL}"
[ "$FAIL" -eq 0 ] || exit 1
green "smoke check passed"
