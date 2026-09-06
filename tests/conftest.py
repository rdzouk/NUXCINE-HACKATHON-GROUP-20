"""Test fixtures.

Phase 0 tests are contract tests. They exercise the app object directly and
touch neither Postgres nor Redis, so they run in CI without a stack.

The environment is populated before app.config is imported, because Settings
validates at import time and now requires every secret to be present and
distinct. Values here are test fixtures, not credentials: they never leave
this process and no deployment reads them.
"""

from __future__ import annotations

import os

import pytest

_TEST_ENV = {
    "APP_ENV": "test",
    "CORS_ORIGINS": "http://localhost:5173",
    "POSTGRES_PASSWORD": "test_password_not_used_no_db_in_these_tests",
    "JWT_SECRET": "test_jwt_secret_0000000000000000000000000000",
    "QUOTE_HMAC_SECRET": "test_quote_secret_1111111111111111111111111",
    "SHARE_TOKEN_SECRET": "test_share_secret_2222222222222222222222222",
    "KYC_ENCRYPTION_KEY": "test_kyc_key_3333333333333333333333333333333",
}
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
