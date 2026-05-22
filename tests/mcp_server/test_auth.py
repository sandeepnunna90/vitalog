"""Tests for MCP OAuth 2.0 auth handlers and BearerMiddleware."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from src.mcp_server.auth import (
    BearerMiddleware,
    _auth_codes,
    authorize_handler,
    oauth_metadata_handler,
    token_handler,
)
from src.persistence.models import PatientRow

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/.well-known/oauth-authorization-server", oauth_metadata_handler),
            Route("/authorize", authorize_handler),
            Route("/token", token_handler, methods=["POST"]),
        ]
    )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=True)


# ── oauth_metadata_handler ───────────────────────────────────────────────────


def test_metadata_returns_required_fields(client: TestClient) -> None:
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("issuer", "authorization_endpoint", "token_endpoint", "response_types_supported"):
        assert key in body


def test_metadata_endpoints_use_base_url(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BASE_URL", "https://example.com")
    resp = client.get("/.well-known/oauth-authorization-server")
    body = resp.json()
    assert body["authorization_endpoint"] == "https://example.com/authorize"
    assert body["token_endpoint"] == "https://example.com/token"  # noqa: S105


# ── authorize_handler ────────────────────────────────────────────────────────


def test_authorize_missing_params_returns_400(client: TestClient) -> None:
    resp = client.get("/authorize")
    assert resp.status_code == 400


def test_authorize_missing_state_returns_400(client: TestClient) -> None:
    resp = client.get(
        "/authorize",
        params={"code_challenge": "abc", "redirect_uri": "http://localhost:9000/cb"},
    )
    assert resp.status_code == 400


def test_authorize_non_localhost_redirect_uri_returns_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example.com")
    resp = client.get(
        "/authorize",
        params={
            "code_challenge": "abc",
            "state": "xyz",
            "redirect_uri": "https://evil.com/steal",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_authorize_valid_params_redirects_to_supabase(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    resp = client.get(
        "/authorize",
        params={
            "code_challenge": "mychallenge",
            "state": "mystate",
            "redirect_uri": "http://127.0.0.1:9000/cb",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "supabase.co" in location
    assert "provider=google" in location
    assert "code_challenge=" in location


# ── token_handler ─────────────────────────────────────────────────────────────


def test_token_unknown_code_returns_invalid_grant(client: TestClient) -> None:
    resp = client.post("/token", data={"code": "nonexistent", "code_verifier": "v"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_token_missing_params_returns_invalid_request(client: TestClient) -> None:
    resp = client.post("/token", data={"code": "abc"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


def test_token_valid_code_returns_access_token(client: TestClient) -> None:
    api_key = uuid.uuid4()
    code = "test-auth-code-123"
    _auth_codes[code] = api_key
    try:
        resp = client.post("/token", data={"code": code, "code_verifier": "v"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == str(api_key)
        assert body["token_type"] == "bearer"  # noqa: S105
    finally:
        _auth_codes.pop(code, None)


def test_token_code_is_single_use(client: TestClient) -> None:
    api_key = uuid.uuid4()
    code = "single-use-code"
    _auth_codes[code] = api_key
    client.post("/token", data={"code": code, "code_verifier": "v"})
    resp = client.post("/token", data={"code": code, "code_verifier": "v"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


# ── BearerMiddleware ──────────────────────────────────────────────────────────


def _echo_app(scope: dict, receive, send) -> None:  # type: ignore[type-arg]
    """Minimal ASGI app that returns 200 OK."""

    async def _inner(scope: dict, receive, send) -> None:  # type: ignore[type-arg]
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"2")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    return _inner(scope, receive, send)  # type: ignore[return-value]


@pytest.fixture()
def bearer_client() -> TestClient:
    return TestClient(BearerMiddleware(_echo_app), raise_server_exceptions=True)


def test_bearer_non_sse_path_passes_through(bearer_client: TestClient) -> None:
    resp = bearer_client.get("/health")
    assert resp.status_code == 200


def test_bearer_sse_missing_auth_header_returns_401(bearer_client: TestClient) -> None:
    resp = bearer_client.get("/sse")
    assert resp.status_code == 401
    assert "Bearer" in resp.headers.get("www-authenticate", "")


def test_bearer_sse_non_bearer_auth_returns_401(bearer_client: TestClient) -> None:
    resp = bearer_client.get("/sse", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


def test_bearer_sse_malformed_uuid_returns_401(bearer_client: TestClient) -> None:
    resp = bearer_client.get("/sse", headers={"Authorization": "Bearer not-a-uuid"})
    assert resp.status_code == 401


def test_bearer_sse_unknown_token_returns_401(bearer_client: TestClient) -> None:
    unknown_key = uuid.uuid4()
    mock_container = MagicMock()
    mock_container.patient_repo.get_by_api_key.return_value = None
    with patch("src.mcp_server.auth.build_container", return_value=mock_container):
        resp = bearer_client.get("/sse", headers={"Authorization": f"Bearer {unknown_key}"})
    assert resp.status_code == 401


def test_bearer_sse_valid_token_passes_through(bearer_client: TestClient) -> None:
    api_key = uuid.uuid4()
    patient_id = uuid.uuid4()
    mock_row = MagicMock(spec=PatientRow)
    mock_row.patient_id = patient_id
    mock_container = MagicMock()
    mock_container.patient_repo.get_by_api_key.return_value = mock_row
    with patch("src.mcp_server.auth.build_container", return_value=mock_container):
        resp = bearer_client.get("/sse", headers={"Authorization": f"Bearer {api_key}"})
    assert resp.status_code == 200
