#!/usr/bin/env bash
#
# Bring the stack up from cold and report the public URL.
#
# Idempotent: safe to run repeatedly. Generates .env with fresh secrets on
# first run and never overwrites an existing one.

set -euo pipefail

cd "$(dirname "$0")/.."

./scripts/gen_secrets.sh

echo "building and starting the stack"
docker compose up -d --build

echo "waiting for the api to become healthy"
for _ in $(seq 1 60); do
    if curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo
echo "local:  http://localhost:8000/api/v1"

# A quick tunnel prints its generated hostname once; a named tunnel does not,
# because the hostname is the one configured in the dashboard.
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ] && ! grep -qE '^CLOUDFLARE_TUNNEL_TOKEN=.+' .env 2>/dev/null; then
    echo -n "public: "
    for _ in $(seq 1 30); do
        url=$(docker compose logs cloudflared 2>/dev/null \
              | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' \
              | tail -1 || true)
        if [ -n "$url" ]; then
            echo "${url}/api/v1"
            break
        fi
        sleep 2
    done
    [ -n "${url:-}" ] || echo "(not ready yet, check: docker compose logs cloudflared)"
else
    echo "public: the hostname configured for your named tunnel"
fi
