"""Token, Host, and Origin checks for HTTP and WebSocket requests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from alfred_ui.app import create_app
from alfred_ui.security import TokenPolicy, _hostname
from alfred_ui.workspace import WorkspaceContext


@pytest.fixture
def anonymous(workspace: Path) -> TestClient:
    app = create_app(
        WorkspaceContext(workspace),
        policy=TokenPolicy(token="secret", cookie_name="alfred_ui_token_1"),
        allowed_hosts=("testserver",),
        allowed_origins=("http://localhost:5173",),
        static_directory=None,
    )
    return TestClient(app, follow_redirects=False)


def test_api_requires_the_token(anonymous: TestClient) -> None:
    assert anonymous.get("/api/snapshot").status_code == 401
    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/auth/status").json() == {"required": True, "authenticated": False}
    assert anonymous.get("/api/snapshot", headers={"X-Alfred-Token": "secret"}).status_code == 200
    assert anonymous.get("/api/snapshot", headers={"X-Alfred-Token": "wrong"}).status_code == 401


def test_link_token_becomes_a_strict_cookie(anonymous: TestClient) -> None:
    response = anonymous.get("/?token=secret&tab=plan")
    assert response.status_code == 303
    assert response.headers["location"] == "/?tab=plan"
    cookie = response.headers["set-cookie"]
    assert cookie == "alfred_ui_token_1=secret; Path=/; HttpOnly; SameSite=Strict"
    signed = anonymous.get("/api/snapshot", headers={"Cookie": "alfred_ui_token_1=secret"})
    assert signed.status_code == 200
    rejected = anonymous.get("/?token=nope")
    assert rejected.headers["location"] == "/?signin=invalid"
    assert "set-cookie" not in rejected.headers


def test_login_sets_the_cookie(anonymous: TestClient) -> None:
    assert anonymous.post("/api/auth/login", json={"token": "nope"}).status_code == 401
    accepted = anonymous.post("/api/auth/login", json={"token": " secret "})
    assert accepted.status_code == 200
    assert accepted.headers["set-cookie"].startswith("alfred_ui_token_1=secret;")


def test_hosts_and_origins(anonymous: TestClient) -> None:
    token = {"X-Alfred-Token": "secret"}
    assert (
        anonymous.get("/api/snapshot", headers={**token, "Host": "evil.example"}).status_code == 403
    )
    assert (
        anonymous.get("/api/snapshot", headers={**token, "Host": "localhost:8765"}).status_code
        == 200
    )
    assert (
        anonymous.get("/api/snapshot", headers={**token, "Host": "[::1]:8765"}).status_code == 200
    )
    cross = anonymous.post(
        "/api/coordinator/once", headers={**token, "Origin": "http://evil.example"}
    )
    assert cross.status_code == 403
    same = anonymous.post("/api/coordinator/once", headers={**token, "Origin": "http://testserver"})
    assert same.status_code == 200
    dev = anonymous.post(
        "/api/coordinator/once", headers={**token, "Origin": "http://localhost:5173"}
    )
    assert dev.status_code == 200


def test_websockets_need_the_token(anonymous: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), anonymous.websocket_connect("/api/live"):
        pass
    with anonymous.websocket_connect("/api/live?token=secret") as socket:
        assert socket.receive_json()["type"] == "snapshot"
    with (
        pytest.raises(WebSocketDisconnect),
        anonymous.websocket_connect(
            "/api/live?token=secret", headers={"Origin": "http://evil.example"}
        ),
    ):
        pass


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("localhost:80", "localhost"),
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]:9", "::1"),
        ("::1", "::1"),
        ("[bad", ""),
    ],
)
def test_hostname(header: str, expected: str) -> None:
    assert _hostname(header) == expected


def test_open_policy_allows_everything() -> None:
    assert TokenPolicy(token=None).valid("") is True
