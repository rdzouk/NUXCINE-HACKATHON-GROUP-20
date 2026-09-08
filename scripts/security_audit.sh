#!/usr/bin/env bash
#
# The Phase 7 security audit, as one command.
#
#   ./scripts/security_audit.sh
#
# Dependency vulnerabilities, secrets in git history, secrets on disk, and the
# production guards. Run before the demo and after any dependency change.
#
# Written as a script rather than a checklist because a checklist is a claim
# and a script is evidence. "We ran pip-audit" is worth nothing to a jury
# without the output.
#
# gitleaks is invoked as a native binary, never through `docker run -v`. On
# Docker Desktop with WSL, a bind mount of $(pwd) can resolve to the *Windows*
# working directory rather than the Linux one, which silently scans a
# completely different repository and reports a clean or dirty result for
# somebody else's code. That happened during Phase 7: the first scan reported
# four leaks belonging to an unrelated project.

set -uo pipefail

cd "$(dirname "$0")/.."

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'
RESET=$'\033[0m'

failed=0
# Not /tmp: a `wsl --shutdown` wipes it, and the audit then reports
# "gitleaks not found" as a warning, which reads like the scan was skipped
# on purpose rather than because a binary vanished.
GITLEAKS="${GITLEAKS:-$(command -v gitleaks 2>/dev/null || echo "$HOME/.local/bin/gitleaks")}"
PY="${PY:-.venv/bin/python}"

step() { printf '\n%s=== %s ===%s\n' "$DIM" "$1" "$RESET"; }
ok()   { printf '%s  PASS%s  %s\n' "$GREEN" "$RESET" "$1"; }
bad()  { printf '%s  FAIL%s  %s\n' "$RED" "$RESET" "$1"; failed=$((failed + 1)); }
warn() { printf '%s  WARN%s  %s\n' "$YELLOW" "$RESET" "$1"; }

# ------------------------------------------------------ dependencies ----
step "dependency vulnerabilities (pip-audit)"
if [ -x "$PY" ]; then
    if "$PY" -m pip_audit -r requirements.lock.txt --progress-spinner off; then
        ok "no known vulnerabilities in the locked dependencies"
    else
        bad "pip-audit reported vulnerabilities, see above"
    fi
else
    warn "no venv at $PY, skipping pip-audit"
fi

# --------------------------------------------------- secrets in history ----
step "secrets in git history (gitleaks)"
if [ -x "$GITLEAKS" ]; then
    # Confirms which repository is actually being scanned. The whole reason
    # this line exists is the bind-mount incident described at the top.
    printf '%s  scanning %s (remote: %s)%s\n' "$DIM" "$(pwd)" \
        "$(git remote get-url origin 2>/dev/null || echo none)" "$RESET"

    if "$GITLEAKS" detect --source=. --redact --no-banner 2>&1 | tail -3; then
        ok "no secrets committed to git history"
    else
        bad "gitleaks found secrets in history; rotate them and rewrite"
    fi
else
    warn "gitleaks not found; set GITLEAKS=/path/to/gitleaks"
fi

# ------------------------------------------------------ secrets on disk ----
step "secrets on disk stay out of git"
if git check-ignore -q .env; then
    ok ".env is gitignored"
else
    bad ".env is NOT gitignored; real secrets are one commit from being public"
fi

for path in .venv osrm-data; do
    if git check-ignore -q "$path" 2>/dev/null; then
        ok "$path is gitignored"
    else
        warn "$path is not gitignored"
    fi
done

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    bad ".env is TRACKED by git"
else
    ok ".env is not tracked"
fi

# ------------------------------------------------- production posture ----
# Read out of the code rather than asserted in prose, so this cannot drift.
step "production guards"

check_guard() {
    local label="$1" pattern="$2" file="$3"
    if grep -q "$pattern" "$file"; then
        ok "$label"
    else
        bad "$label"
    fi
}

check_guard "API docs are disabled in production" \
    'docs_url=None if settings.is_production' app/main.py
check_guard "OpenAPI schema is withheld in production" \
    'openapi_url=None if settings.is_production' app/main.py
check_guard "the driver simulator needs DEBUG and a non-production env" \
    'settings.debug and not settings.is_production' app/api/v1/dev.py
check_guard "the console SMS sender refuses to run in production" \
    'if settings.is_production' app/services/sms.py
check_guard "test phone numbers are refused in production" \
    'settings.is_production or not settings.allow_test_numbers' app/security/phone.py
check_guard "a wildcard CORS origin is rejected at boot" \
    'CORS_ORIGINS must be an explicit allow-list' app/config.py
check_guard "weak signing secrets are rejected at boot" \
    '_reject_weak_secret' app/config.py

# An unhandled exception must never return its own text. The handler logs
# server-side and answers with a fixed envelope, so a stack trace cannot reach
# a client in any environment rather than only outside production.
if grep -A 4 'async def _unhandled' app/errors/handlers.py | grep -q 'str(exc)'; then
    bad "the unhandled-exception handler leaks exception text to the client"
else
    ok "unhandled exceptions return a generic envelope, never their own text"
fi

# ------------------------------------------------------------ summary ----
printf '\n-----------------------------------------\n'
if [ "$failed" -gt 0 ]; then
    printf '%s%d security check(s) failed%s\n' "$RED" "$failed" "$RESET"
    exit 1
fi
printf '%severy security check passed%s\n' "$GREEN" "$RESET"
