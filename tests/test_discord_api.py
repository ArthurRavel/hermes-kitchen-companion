from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError

import pytest

from kitchen_companion import discord_api
from kitchen_companion.bootstrap import BootstrapConfig, bootstrap
from kitchen_companion.discord_api import DiscordClient, DiscordError, UrllibTransport

TEST_GUILD_ID = str(10**17 + 2)


def test_api_failure_does_not_expose_credential_or_body(monkeypatch: pytest.MonkeyPatch) -> None:
    credential = secrets.token_urlsafe(32)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise HTTPError(args[0].full_url, 500, credential, {}, None)

    monkeypatch.setattr(discord_api, "urlopen", fail)
    with pytest.raises(DiscordError) as error:
        UrllibTransport().request("GET", "/guilds/example/channels", token=credential)
    assert credential not in str(error.value)
    assert "500" in str(error.value)


def test_rate_limit_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    calls = 0

    def rate_limit_then_ok(request: Any, timeout: float) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 429, "limited", {"Retry-After": "0.25"}, None)

        class Response:
            def __enter__(self) -> Response:
                return self

            def __exit__(self, *args: Any) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok": true}'

        return Response()

    monkeypatch.setattr(discord_api, "urlopen", rate_limit_then_ok)
    result = UrllibTransport(sleep=waits.append).request(
        "GET", "/guilds/example/channels", token=secrets.token_urlsafe(24)
    )
    assert result == {"ok": True}
    assert calls == 2
    assert waits == [0.25]


def test_persistent_rate_limit_is_clear_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def always_limited(request: Any, timeout: float) -> Any:
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, 429, "limited", {"Retry-After": "0"}, None)

    monkeypatch.setattr(discord_api, "urlopen", always_limited)
    with pytest.raises(DiscordError, match="persisted after retries"):
        UrllibTransport(sleep=lambda _: None).request(
            "GET", "/guilds/example/channels", token=secrets.token_urlsafe(24)
        )
    assert calls == 4


def test_timeout_is_reported_without_url_or_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    credential = secrets.token_urlsafe(24)

    def timeout(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutError(credential)

    monkeypatch.setattr(discord_api, "urlopen", timeout)
    with pytest.raises(DiscordError) as error:
        UrllibTransport().request("GET", "/guilds/example/channels", token=credential)
    assert credential not in str(error.value)


@pytest.fixture
def fake_discord_server(monkeypatch: pytest.MonkeyPatch) -> Any:
    state: dict[str, Any] = {"channels": [], "counter": 0, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            state["requests"].append(("GET", self.path))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state["channels"]).encode())

        def do_POST(self) -> None:
            state["requests"].append(("POST", self.path))
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            state["counter"] += 1
            resource = {**payload, "id": f"server-{state['counter']}"}
            state["channels"].append(resource)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resource).encode())

        def do_PATCH(self) -> None:
            state["requests"].append(("PATCH", self.path))
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(discord_api, "API_BASE", f"http://127.0.0.1:{server.server_port}/api/v10")
    yield state
    server.shutdown()
    thread.join()


def test_end_to_end_against_local_fake_http_server(fake_discord_server: dict[str, Any]) -> None:
    client = DiscordClient(token=secrets.token_urlsafe(24), transport=UrllibTransport())
    first = bootstrap(client, BootstrapConfig(guild_id=TEST_GUILD_ID))
    second = bootstrap(client, BootstrapConfig(guild_id=TEST_GUILD_ID))

    assert len(first["created"]) == 6
    assert second["created"] == []
    assert len(second["channel_ids"]) == 5
    assert [method for method, _ in fake_discord_server["requests"]].count("POST") == 6
    assert all(
        path.endswith(f"/guilds/{TEST_GUILD_ID}/channels")
        for _, path in fake_discord_server["requests"]
    )
