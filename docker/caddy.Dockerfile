# Caddy with its configuration and the built frontend baked in, not mounted.
#
# Two reasons, one principled and one practical.
#
# Principled: neither the reverse-proxy config nor a compiled bundle is a
# secret, and an immutable image is the better artifact. What ran is exactly
# what was built.
#
# Practical: Docker Desktop's WSL bind mounts proved unreliable on this
# machine, serving a stale snapshot of the repository that survived a full
# engine and WSL restart. That warning was already written here for the
# Caddyfile, and then `./dist` was bind-mounted anyway during Tier 1 and hit
# the identical failure: after a host restart Docker had rewritten the source
# to /run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/Ubuntu/<hash>, an
# empty directory, so every page answered 404 while `dist/` sat full on the
# host. Build contexts are streamed by the CLI and are unaffected.
#
# So the loop after a UI change is two commands, not one:
#
#     npm run build
#     docker compose up -d --build caddy
#
# The second takes a few seconds because it is a COPY over a cached base. That
# is a fair price for a stack that cannot silently serve nothing.

FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile

# The compiled single-page app. Built on the host by `npm run build`, because
# running Node inside this image would mean shipping a toolchain to serve
# static files.
COPY dist /srv/web

RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || true
