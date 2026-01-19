import json
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import httpx

from .config import StravaEnv, load_tokens, save_tokens


AUTH_BASE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE = "activity:read_all"


def build_authorize_url(env: StravaEnv) -> str:
    params = {
        "client_id": env.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "approval_prompt": "auto",
    }
    return f"{AUTH_BASE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(env: StravaEnv, code: str) -> Dict[str, Any]:
    payload = {
        "client_id": env.client_id,
        "client_secret": env.client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data=payload)
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(env: StravaEnv, refresh_token: str) -> Dict[str, Any]:
    payload = {
        "client_id": env.client_id,
        "client_secret": env.client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data=payload)
        resp.raise_for_status()
        return resp.json()


def token_is_expired(tokens: Dict[str, Any], skew_seconds: int = 60) -> bool:
    expires_at = tokens.get("expires_at")
    if not expires_at:
        return True
    return int(expires_at) <= int(time.time()) + skew_seconds


class _CodeHandler(BaseHTTPRequestHandler):
    server_version = "StravaAuth/1.0"
    protocol_version = "HTTP/1.1"
    auth_code: Optional[str] = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            _CodeHandler.auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization received. You can close this window.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def get_auth_code_via_local_server(timeout_seconds: int = 180) -> Optional[str]:
    _CodeHandler.auth_code = None
    try:
        server = HTTPServer(("localhost", 8080), _CodeHandler)
    except OSError:
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    start = time.time()
    try:
        while time.time() - start < timeout_seconds:
            if _CodeHandler.auth_code:
                return _CodeHandler.auth_code
            time.sleep(0.2)
        return None
    finally:
        server.shutdown()
        server.server_close()


def run_interactive_auth(env: StravaEnv) -> Dict[str, Any]:
    auth_url = build_authorize_url(env)
    print("Open this URL to authorize the application:")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    code = get_auth_code_via_local_server()
    if not code:
        code = input("Paste the authorization code from the URL: ").strip()
    token_data = exchange_code_for_tokens(env, code)
    tokens = {
        "refresh_token": token_data.get("refresh_token"),
        "access_token": token_data.get("access_token"),
        "expires_at": token_data.get("expires_at"),
        "athlete_id": (token_data.get("athlete") or {}).get("id"),
    }
    save_tokens(tokens)
    return tokens


def ensure_valid_tokens(env: StravaEnv, tokens: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if tokens is None:
        tokens = load_tokens()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("No refresh token found. Run auth first.")
    if token_is_expired(tokens):
        token_data = refresh_access_token(env, refresh_token)
        tokens.update(
            {
                "refresh_token": token_data.get("refresh_token", refresh_token),
                "access_token": token_data.get("access_token"),
                "expires_at": token_data.get("expires_at"),
                "athlete_id": (token_data.get("athlete") or {}).get("id"),
            }
        )
        save_tokens(tokens)
    return tokens
