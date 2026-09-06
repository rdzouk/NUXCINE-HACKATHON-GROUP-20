#!/usr/bin/env bash
#
# Generate .env with fresh secrets. Idempotent and non-destructive: it only
# replaces values that are still the .env.example placeholders, so running it
# twice never rotates a key that something is already signed with.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "created .env from .env.example"
fi

replace_if_placeholder() {
    local key="$1" value="$2"
    local current
    current=$(grep -E "^${key}=" .env | head -1 | cut -d= -f2- || true)
    case "$current" in
        ""|replace_with*|*change_me*)
            # The value is hex, so it contains no sed metacharacters.
            sed -i "s|^${key}=.*|${key}=${value}|" .env
            echo "  set ${key} (${#value} chars)"
            ;;
        *)
            echo "  kept ${key} (already set, ${#current} chars)"
            ;;
    esac
}

echo "secrets:"
for key in JWT_SECRET QUOTE_HMAC_SECRET SHARE_TOKEN_SECRET KYC_ENCRYPTION_KEY; do
    replace_if_placeholder "$key" "$(openssl rand -hex 32)"
done
replace_if_placeholder POSTGRES_PASSWORD "$(openssl rand -hex 16)"

chmod 600 .env
echo "done. .env is mode $(stat -c %a .env) and gitignored."
