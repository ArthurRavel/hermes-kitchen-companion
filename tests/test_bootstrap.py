from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import pytest

from kitchen_companion.bootstrap import BootstrapConfig, bootstrap, save_state
from kitchen_companion.discord_api import DiscordClient, DiscordError

CATEGORY = {"id": "cat-1", "name": "🍳 Chez Dobby", "type": 4, "parent_id": None}
TEST_GUILD_ID = str(10**17 + 1)
EXPECTED = [
    ("💬・discussion", 0),
    ("💡・idées-repas", 0),
    ("🎬・reels", 0),
    ("📖・carnet", 15),
    ("🛒・courses", 0),
]


class FakeTransport:
    def __init__(self, channels: list[dict[str, Any]] | None = None) -> None:
        self.channels = list(channels or [])
        self.created: list[dict[str, Any]] = []
        self.reorders: list[list[dict[str, Any]]] = []
        self.calls: list[str] = []

    def request(self, method: str, path: str, *, token: str, body: Any = None) -> Any:
        self.calls.append(method)
        if method == "GET":
            return list(self.channels)
        if method == "POST":
            resource = {**body, "id": f"new-{len(self.created) + 1}"}
            self.channels.append(resource)
            self.created.append(resource)
            return resource
        if method == "PATCH":
            self.reorders.append(body)
            return None
        raise AssertionError(f"Unexpected method: {method}")


def make_client(transport: FakeTransport) -> DiscordClient:
    return DiscordClient(token=secrets.token_urlsafe(24), transport=transport)


def test_creates_category_and_default_channels_in_order() -> None:
    transport = FakeTransport()
    result = bootstrap(
        make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID, sync_order=True)
    )

    assert [item["name"] for item in result["created"]] == [
        "🍳 Chez Dobby",
        *[n for n, _ in EXPECTED],
    ]
    assert [item["type"] for item in transport.created] == [4, 0, 0, 0, 15, 0]
    assert [item["position"] for item in transport.reorders[0][1:]] == [1, 2, 3, 4, 5]
    assert result["channel_ids"]["notebook"] == "new-5"


def test_partial_existing_state_creates_only_missing_resources() -> None:
    channels = [
        CATEGORY,
        {"id": "discussion-id", "name": EXPECTED[0][0], "type": 0, "parent_id": "cat-1"},
    ]
    transport = FakeTransport(channels)
    result = bootstrap(make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID))

    assert len(transport.created) == 4
    assert result["channel_ids"]["discussion"] == "discussion-id"
    assert len(result["existing"]) == 2


def test_rerun_is_idempotent_and_keeps_channel_ids() -> None:
    transport = FakeTransport()
    client = make_client(transport)
    bootstrap(client, BootstrapConfig(guild_id=TEST_GUILD_ID))
    created = list(transport.created)
    result = bootstrap(client, BootstrapConfig(guild_id=TEST_GUILD_ID))

    assert transport.created == created
    assert result["created"] == []
    assert len(result["channel_ids"]) == 5


def test_forum_channel_is_created_as_forum_type() -> None:
    transport = FakeTransport()
    bootstrap(make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID))
    forum = next(row for row in transport.created if row["name"] == "📖・carnet")
    assert forum["type"] == 15


def test_duplicate_exact_channel_fails_before_any_mutation() -> None:
    channels = [
        CATEGORY,
        {"id": "one", "name": EXPECTED[0][0], "type": 0, "parent_id": "cat-1"},
        {"id": "two", "name": EXPECTED[0][0], "type": 0, "parent_id": "cat-1"},
    ]
    transport = FakeTransport(channels)
    with pytest.raises(DiscordError, match="rename duplicates"):
        bootstrap(make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID))
    assert transport.created == []


def test_duplicate_category_fails_without_mutation() -> None:
    transport = FakeTransport([CATEGORY, {**CATEGORY, "id": "cat-2"}])
    with pytest.raises(DiscordError, match="categories"):
        bootstrap(make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID))
    assert transport.created == []


def test_dry_run_is_offline_and_has_structured_plan() -> None:
    transport = FakeTransport()
    result = bootstrap(
        make_client(transport),
        BootstrapConfig(guild_id=TEST_GUILD_ID),
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert len(result["planned"]) == 6
    assert result["planned"][4]["type"] == "forum"
    assert transport.calls == []


def test_language_and_custom_category() -> None:
    transport = FakeTransport()
    result = bootstrap(
        make_client(transport),
        BootstrapConfig(guild_id=TEST_GUILD_ID, category_name="Kitchen", language="en"),
    )
    assert result["category"]["name"] == "Kitchen"
    assert any(row["name"] == "📖・notebook" for row in transport.created)


def test_state_file_contains_only_non_secret_mapping(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    summary = bootstrap(make_client(FakeTransport()), BootstrapConfig(guild_id=TEST_GUILD_ID))
    save_state(path, summary)
    text = path.read_text()
    assert "channel_ids" in text
    assert "token" not in text.casefold()
    assert path.stat().st_mode & 0o777 == 0o600


def test_invalid_guild_id_is_rejected_before_network_request() -> None:
    transport = FakeTransport()
    with pytest.raises(ValueError, match="17 to 20 digit"):
        bootstrap(make_client(transport), BootstrapConfig(guild_id="invalid/path"))
    assert transport.calls == []


def test_unrelated_channels_are_preserved() -> None:
    unrelated = {"id": "outside", "name": "General", "type": 0, "parent_id": None}
    transport = FakeTransport([unrelated])
    bootstrap(make_client(transport), BootstrapConfig(guild_id=TEST_GUILD_ID))
    assert unrelated in transport.channels
    assert all(method in {"GET", "POST"} for method in transport.calls)
