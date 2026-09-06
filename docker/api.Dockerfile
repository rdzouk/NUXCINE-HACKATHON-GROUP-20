# syntax=docker/dockerfile:1
#
# Two stages so the final image carries no compiler and no build headers.
# That is not cosmetic: a container with gcc in it is a much more useful
# foothold than one without.

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# The lock file is preferred when present; the glob keeps the build working
# before it has been generated.
COPY requirements.txt requirements.lock.txt* ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && if [ -f requirements.lock.txt ]; then \
         /opt/venv/bin/pip install -r requirements.lock.txt; \
       else \
         /opt/venv/bin/pip install -r requirements.txt; \
       fi


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 vora

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
COPY --chown=vora:vora alembic.ini ./
COPY --chown=vora:vora migrations ./migrations
COPY --chown=vora:vora app ./app

USER vora

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# No --reload here. docker-compose.dev.yml adds it when explicitly opted into.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
