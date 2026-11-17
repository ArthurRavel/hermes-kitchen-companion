"""Idempotent, conservative Discord server scaffolding."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .discord_api import DiscordClient, DiscordError

CHANNELS: dict[str, tuple[str, int]] = {
    "discussion": ("💬・discussion", 0),
    "meal_ideas": ("💡・idées-repas", 0),
    "reels": ("🎬・reels", 0),
    "notebook": ("📖・carnet", 15),
    "shopping": ("🛒・courses", 0),
}
CATEGORY_TYPE = 4


@dataclass(frozen=True)
class BootstrapConfig:
    guild_id: str
    category_name: str = "🍳 Chez Dobby"
    language: str = "fr"
    sync_order: bool = False


def channels_for_language(language: str) -> dict[str, tuple[str, int]]:
    if language == "fr":
        return CHANNELS
    if language == "en":
        return {
            "discussion": ("💬・discussion", 0),
            "meal_ideas": ("💡・meal-ideas", 0),
            "reels": ("🎬・reels", 0),
            "notebook": ("📖・notebook", 15),
            "shopping": ("🛒・shopping", 0),
        }
    raise ValueError("Language must be 'en' or 'fr'.")


def _matches(
    channels: list[dict[str, Any]], name: str, kind: int, parent_id: str | None
) -> list[dict[str, Any]]:
    return [
        c
        for c in channels
        if c.get("name") == name and c.get("type") == kind and c.get("parent_id") == parent_id
    ]


def bootstrap(
    client: DiscordClient,
    config: BootstrapConfig,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create missing managed resources; never delete or adopt ambiguous resources."""
    if not re.fullmatch(r"[0-9]{17,20}", config.guild_id):
        raise ValueError("Discord server ID must be a 17 to 20 digit snowflake.")
    channel_types = channels_for_language(config.language)
    if dry_run:
        return {
            "guild_id": config.guild_id,
            "dry_run": True,
            "planned": [
                {"name": config.category_name, "type": "category"},
                *[
                    {"key": key, "name": name, "type": "forum" if kind == 15 else "text"}
                    for key, (name, kind) in channel_types.items()
                ],
            ],
            "created": [],
            "existing": [],
        }

    channels = client.list_channels(config.guild_id)
    categories = _matches(channels, config.category_name, CATEGORY_TYPE, None)
    if len(categories) > 1:
        raise DiscordError(
            f"Found {len(categories)} categories named {config.category_name!r}; "
            "rename duplicates and retry."
        )
    # Validate every exact match before the first mutation, so ambiguity never leaves
    # a partially scaffolded server.
    if categories:
        category_id = str(categories[0]["id"])
        for name, kind in channel_types.values():
            matches = _matches(channels, name, kind, category_id)
            if len(matches) > 1:
                raise DiscordError(
                    f"Found {len(matches)} matching channels named {name!r} "
                    "in the managed category; "
                    "rename duplicates and retry."
                )

    created: list[dict[str, str]] = []
    existing: list[dict[str, str]] = []
    if categories:
        category = categories[0]
        category_id = str(category["id"])
        existing.append({"name": config.category_name, "id": category_id, "type": "category"})
    else:
        category = client.create_channel(
            config.guild_id, {"name": config.category_name, "type": CATEGORY_TYPE}
        )
        category_id = str(category["id"])
        created.append({"name": config.category_name, "id": category_id, "type": "category"})

    positions: list[dict[str, Any]] = []
    for position, (key, (name, kind)) in enumerate(channel_types.items()):
        found = _matches(channels, name, kind, category_id)
        if len(found) > 1:
            raise DiscordError(
                f"Found {len(found)} matching channels named {name!r} in the managed category; "
                "rename duplicates and retry."
            )
        if found:
            resource = found[0]
            resource_id = str(resource["id"])
            existing.append(
                {
                    "key": key,
                    "name": name,
                    "id": resource_id,
                    "type": "forum" if kind == 15 else "text",
                }
            )
        else:
            resource = client.create_channel(
                config.guild_id,
                {"name": name, "type": kind, "parent_id": category_id},
            )
            resource_id = str(resource["id"])
            created.append(
                {
                    "key": key,
                    "name": name,
                    "id": resource_id,
                    "type": "forum" if kind == 15 else "text",
                }
            )
        positions.append({"id": resource_id, "position": position})

    if config.sync_order:
        client.reorder(
            config.guild_id,
            [
                {"id": category_id, "position": 0},
                *[{"id": row["id"], "position": index + 1} for index, row in enumerate(positions)],
            ],
        )

    return {
        "guild_id": config.guild_id,
        "category": {"name": config.category_name, "id": category_id},
        "dry_run": False,
        "created": created,
        "existing": existing,
        "channel_ids": {row["key"]: row["id"] for row in [*existing, *created] if "key" in row},
    }


def save_state(path: Path, summary: dict[str, Any]) -> None:
    """Write only non-secret IDs as private local state."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "guild_id": summary["guild_id"],
        "category": summary.get("category"),
        "channel_ids": summary.get("channel_ids", {}),
    }
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
