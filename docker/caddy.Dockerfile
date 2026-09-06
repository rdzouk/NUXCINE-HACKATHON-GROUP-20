# Caddy with its configuration baked in rather than bind-mounted.
#
# Two reasons, one principled and one practical.
#
# Principled: the reverse-proxy config is not a secret and changes rarely, so
# an immutable image is the better artifact. What ran is exactly what was built.
#
# Practical: Docker Desktop's WSL bind mounts proved unreliable on this machine,
# serving a stale snapshot of the repository that survived a full engine and
# WSL restart. Build contexts are streamed by the CLI and are unaffected, so
# copying the file in sidesteps the problem entirely. A stack that depends on
# nothing but its build context is one less thing to debug at hour forty.
#
# Editing the Caddyfile therefore requires `docker compose up -d --build caddy`.

FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile

RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || true
