"""Shared HTTP client for the Seerr API, authenticated with a session cookie.

Seerr (a Jellyseerr/Overseerr fork) issues an instance-wide API key that only an
administrator can create, so tools instead sign in with the user's Jellyfin
credentials and reuse the resulting express-session cookie. The cookie is cached
at the plugin root; sessions last 30 days server-side.

Tools live one directory below the plugin root and run with their own directory
as the working directory, so each entrypoint must put the plugin root on
sys.path before importing this module, e.g.:

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from seerr_client import SeerrClient

"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPMessage
from http.cookies import SimpleCookie
from pathlib import Path
from typing import IO, NoReturn

CONFIG_PATH = Path("../config.json")
COOKIE_PATH = Path("../.seerr_session_cookie")

# express-session is mounted at /api without a cookie name override, so the
# cookie is express-session's default name.
SESSION_COOKIE_NAME = "connect.sid"

# One tool invocation can make several requests -- create_request, for example,
# posts the request and then looks up its title -- and the plugin runner kills
# the process after 30 seconds. A flat per-call timeout keeps a single stalled
# connection well inside that limit instead of consuming the whole budget.
REQUEST_TIMEOUT_SECONDS = 10

MediaRequestStatus: dict[int, str] = {
    1: "pending",
    2: "approved",
    3: "declined",
    4: "failed",
    5: "completed",
}

MediaStatus: dict[int, str] = {
    1: "unknown",
    2: "pending",
    3: "processing",
    4: "partially_available",
    5: "available",
    6: "blocklisted",
    7: "deleted",
}


def _fail(error: urllib.error.HTTPError) -> NoReturn:
    """Surface an HTTP error's status and body on stderr and exit non-zero."""
    body = error.read().decode()
    json.dump({"error": f"HTTP {error.code}: {body}"}, sys.stderr)
    sys.exit(1)


def _extract_session_cookie(headers: HTTPMessage) -> str | None:
    """Return the connect.sid value from a response's Set-Cookie headers."""
    for header in headers.get_all("Set-Cookie") or []:
        cookie = SimpleCookie()
        cookie.load(header)
        if SESSION_COOKIE_NAME in cookie:
            return cookie[SESSION_COOKIE_NAME].value
    return None


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Fail on every redirect instead of following it.

    urllib's default redirect handler re-sends the original request headers to
    the redirect target, session Cookie included, so a cross-origin redirect
    would hand the session to another host. Classifying same-origin versus
    cross-origin redirects is not worth the complexity: refusing all of them is
    simpler, and the error names the address the user should configure instead.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> NoReturn:
        # newurl carries the full redirected path, but api_url is a base URL, so
        # only the scheme and host are useful advice to the user.
        parsed = urllib.parse.urlsplit(newurl)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        print(
            f"HTTP {code} redirect to {newurl}. Refusing to follow it because "
            "urllib would forward the session cookie to that address. Set "
            f"api_url to {origin} in config.json if that is the right instance.",
            file=sys.stderr,
        )
        sys.exit(1)


# Every request carries the session cookie, so login and authenticated calls
# alike must go through this opener rather than urllib's default one.
_OPENER = urllib.request.build_opener(_RefuseRedirects)


class SeerrClient:
    """Cookie-authenticated Seerr API client.

    Seerr rejects an unauthenticated or expired session with HTTP 403 (not 401,
    because isAuthenticated() rejects with 403), but it also answers a
    route-level refusal such as a quota limit, a permission denial, or a
    blocklisted title with 403. A 403 triggers a fresh login and one retry only
    when the cookie came from the cache and might therefore be stale; a cookie
    obtained by a login during this invocation cannot have expired, so its 403
    is surfaced as the real error.
    """

    def __init__(self, api_url: str, username: str, password: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self._cookie: str | None = None
        # Whether the current cookie came from a login during this invocation
        # rather than the on-disk cache. Only a cached cookie can have expired,
        # so this decides whether a 403 is worth a fresh login and a replay.
        self._cookie_from_login = False

    @classmethod
    def from_config(cls) -> "SeerrClient":
        """Build a client from the plugin's ../config.json."""
        config = json.loads(CONFIG_PATH.read_text())
        return cls(
            config["api_url"],
            config["jellyfin_username"],
            config["jellyfin_password"],
        )

    def get(self, path: str) -> dict:
        return json.loads(self._send("GET", path))

    def post(self, path: str, body: dict) -> dict:
        return json.loads(self._send("POST", path, body))

    def delete(self, path: str) -> None:
        # A successful DELETE returns 204 with an empty body, so the response is
        # deliberately discarded rather than parsed as JSON.
        self._send("DELETE", path)

    def _ensure_session(self) -> None:
        if self._cookie is not None:
            return
        cached = self._read_cached_session()
        if cached is not None:
            self._cookie = cached
            self._cookie_from_login = False
            return
        self._login()

    def _read_cached_session(self) -> str | None:
        """Return the cached cookie, or None if it must not be reused.

        The cache records the api_url and username the cookie was issued for,
        because a cookie is only valid for one account on one instance. If the
        user edits config.json, the mismatch forces a fresh login instead of
        silently acting as the previous account or sending a cookie to a new
        host. A malformed cache (such as a legacy plain-text one) is treated the
        same as no cache at all.
        """
        if not COOKIE_PATH.exists():
            return None
        try:
            cache = json.loads(COOKIE_PATH.read_text())
            cookie = cache["cookie"]
            api_url = cache["api_url"]
            username = cache["username"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        if not isinstance(cookie, str):
            return None
        if api_url != self.api_url or username != self.username:
            return None
        return cookie

    def _login(self) -> None:
        # The Seerr web UI sends the username again as the email, and rejects a
        # request that carries a hostname when the instance already has Jellyfin
        # configured, so no hostname is sent here.
        body = json.dumps(
            {
                "username": self.username,
                "password": self.password,
                "email": self.username,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.api_url}/api/v1/auth/jellyfin",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                cookie = _extract_session_cookie(response.headers)
        except urllib.error.HTTPError as error:
            _fail(error)
        if cookie is None:
            print(
                "Login succeeded but no connect.sid cookie was set.",
                file=sys.stderr,
            )
            sys.exit(1)
        self._cookie = cookie
        self._cookie_from_login = True
        # The password is deliberately never written to the cache; only the
        # cookie and the identity it was issued for.
        COOKIE_PATH.write_text(
            json.dumps(
                {
                    "cookie": cookie,
                    "api_url": self.api_url,
                    "username": self.username,
                }
            )
        )

    def _send(self, method: str, path: str, body: dict | None = None) -> bytes:
        self._ensure_session()
        try:
            return self._send_once(method, path, body)
        except urllib.error.HTTPError as error:
            # Only a 403 from a cached cookie can mean the cached session
            # expired. Seerr also returns 403 for quota, permission, and
            # blocklist refusals, and a cookie from a login performed earlier in
            # this invocation cannot have expired, so its 403 is a real error
            # and must not trigger a pointless re-login and replay.
            if error.code != 403 or self._cookie_from_login:
                _fail(error)
        # The cached session is missing or expired: log in again and retry the
        # call once. The request never reached its handler, since authentication
        # rejected it first, so replaying it is safe.
        self._login()
        try:
            return self._send_once(method, path, body)
        except urllib.error.HTTPError as retry_error:
            _fail(retry_error)

    def _send_once(self, method: str, path: str, body: dict | None) -> bytes:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Cookie": f"{SESSION_COOKIE_NAME}={self._cookie}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()
