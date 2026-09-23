"""Access control for a local server that can type into agent sessions.

The UI can send keystrokes to tmux sessions, so it guards every API and WebSocket request:

* the ``Host`` header must name an allowed host, which defeats DNS-rebinding attacks;
* a browser ``Origin`` must match the requested host (or an explicitly allowed origin);
* API and WebSocket requests need the access token, supplied once through the printed URL and
  then carried in an HttpOnly, SameSite=Strict cookie (or an ``X-Alfred-Token`` header).
"""

import hmac
from collections.abc import Iterable
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode, urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/auth/status", "/api/auth/login"})
TOKEN_HEADER = "x-alfred-token"


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    """The access token and how browsers carry it."""

    token: str | None
    cookie_name: str = "alfred_ui_token"

    def valid(self, supplied: str) -> bool:
        """Compare a supplied token in constant time; no token means access is open."""
        if not self.token:
            return True
        return bool(supplied) and hmac.compare_digest(supplied.encode(), self.token.encode())

    def supplied(self, headers: Headers, query: dict[str, str]) -> str:
        """Return the token supplied by header, cookie, or query string."""
        header = headers.get(TOKEN_HEADER)
        if header:
            return header
        cookie: SimpleCookie = SimpleCookie()
        try:
            cookie.load(headers.get("cookie", ""))
        except Exception:
            return query.get("token", "")
        morsel = cookie.get(self.cookie_name)
        return morsel.value if morsel is not None else query.get("token", "")

    def authorized(self, headers: Headers, query: dict[str, str]) -> bool:
        """Return whether the request carries the access token."""
        return self.valid(self.supplied(headers, query))

    def cookie_header(self, value: str) -> str:
        """Return a Set-Cookie value for the access token."""
        return f"{self.cookie_name}={value}; Path=/; HttpOnly; SameSite=Strict"


class AccessGuard:
    """ASGI middleware enforcing host, origin, and token checks."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        policy: TokenPolicy,
        allowed_hosts: Iterable[str] = (),
        allowed_origins: Iterable[str] = (),
    ) -> None:
        self.app = app
        self.policy = policy
        self.allowed_hosts = DEFAULT_HOSTS | {host.lower() for host in allowed_hosts}
        self.allowed_origins = {origin.rstrip("/").lower() for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject disallowed requests before they reach the application."""
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        if not self.host_allowed(host):
            await _deny(scope, receive, send, 403, "Host not allowed")
            return
        origin = headers.get("origin")
        method = scope.get("method", "GET")
        cross_origin_sensitive = scope["type"] == "websocket" or method not in {"GET", "HEAD"}
        if origin and cross_origin_sensitive and not self.origin_allowed(origin, host):
            await _deny(scope, receive, send, 403, "Origin not allowed")
            return
        path: str = scope.get("path", "")
        query = dict(parse_qsl(scope.get("query_string", b"").decode("latin-1")))
        if (
            self.policy.token
            and scope["type"] == "http"
            and not path.startswith("/api/")
            and "token" in query
        ):
            await self._exchange_token(scope, send, path, query)
            return
        needs_token = path.startswith("/api/") and path not in PUBLIC_API_PATHS
        if needs_token and not self.policy.authorized(headers, query):
            await _deny(scope, receive, send, 401, "Open the link printed by alfred-ui to sign in")
            return
        await self.app(scope, receive, send)

    def host_allowed(self, host: str) -> bool:
        """Return whether the Host header names an allowed host (port ignored)."""
        name = _hostname(host)
        return bool(name) and name in self.allowed_hosts

    def origin_allowed(self, origin: str, host: str) -> bool:
        """Return whether an Origin is this server itself or an explicitly allowed origin."""
        normalized = origin.rstrip("/").lower()
        if normalized in self.allowed_origins:
            return True
        parsed = urlsplit(normalized)
        return parsed.scheme in {"http", "https"} and parsed.netloc == host.lower()

    async def _exchange_token(
        self, scope: Scope, send: Send, path: str, query: dict[str, str]
    ) -> None:
        """Turn ``?token=`` into a cookie and redirect to the same page without the token."""
        supplied = query.pop("token", "")
        remaining = urlencode(query)
        location = path + (f"?{remaining}" if remaining else "")
        headers = [(b"location", location.encode("latin-1")), (b"cache-control", b"no-store")]
        if self.policy.valid(supplied):
            headers.append((b"set-cookie", self.policy.cookie_header(supplied).encode("latin-1")))
        else:
            location = path + "?" + urlencode({**query, "signin": "invalid"})
            headers[0] = (b"location", location.encode("latin-1"))
        await send({"type": "http.response.start", "status": 303, "headers": headers})
        await send({"type": "http.response.body", "body": b""})


def _hostname(host: str) -> str:
    value = host.strip().lower()
    if value.startswith("["):
        return value[1 : value.find("]")] if "]" in value else ""
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


async def _deny(scope: Scope, receive: Receive, send: Send, status: int, message: str) -> None:
    if scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.close", "code": 4000 + status, "reason": message})
        return
    body = ('{"error": "' + message + '"}').encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
