"""Small, dependency-free Discord REST client with bounded rate-limit retries."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = "https://discord.com/api/v10"


class Transport(Protocol):
    def request(
        self, method: str, path: str, *, token: str, body: dict[str, Any] | None = None
    ) -> Any: ...


class DiscordError(RuntimeError):
    """Safe-to-display Discord API failure; never includes request credentials or bodies."""


@dataclass
class UrllibTransport:
    timeout: float = 10.0
    attempts: int = 4
    sleep: Callable[[float], None] = time.sleep

    def request(
        self, method: str, path: str, *, token: str, body: dict[str, Any] | None = None
    ) -> Any:
        url = f"{API_BASE}{path}"
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(self.attempts):
            request = Request(
                url,
                data=encoded,
                method=method,
                headers={
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "HermesKitchenCompanion/0.1 (+self-hosted)",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                return json.loads(raw) if raw else None
            except HTTPError as exc:
                if exc.code == 429 and attempt + 1 < self.attempts:
                    try:
                        delay = float(exc.headers.get("Retry-After", "1"))
                    except (TypeError, ValueError):
                        delay = 1.0
                    self.sleep(min(max(delay, 0.0), 30.0))
                    continue
                if exc.code == 429:
                    raise DiscordError(
                        "Discord rate limit persisted after retries; try again later."
                    ) from None
                messages = {
                    401: "Discord rejected the bot credential. Check the environment variable "
                    "and try again.",
                    403: "Discord denied this action. Confirm the bot can view the managed "
                    "channels and has Manage Channels permission.",
                    404: "Discord could not find the selected server. Check its ID and bot access.",
                }
                raise DiscordError(
                    messages.get(exc.code, f"Discord API returned HTTP {exc.code}.")
                ) from None
            except (TimeoutError, URLError, OSError):
                raise DiscordError(
                    "Could not reach Discord before the request timed out."
                ) from None
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise DiscordError("Discord returned an unreadable response.") from None
        raise DiscordError("Discord request failed after retries.")


@dataclass
class DiscordClient:
    token: str
    transport: Transport

    def list_channels(self, guild_id: str) -> list[dict[str, Any]]:
        result = self.transport.request("GET", f"/guilds/{guild_id}/channels", token=self.token)
        if not isinstance(result, list):
            raise DiscordError("Discord returned an invalid channel list.")
        return result

    def create_channel(self, guild_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.transport.request(
            "POST", f"/guilds/{guild_id}/channels", token=self.token, body=payload
        )
        if not isinstance(result, dict) or "id" not in result:
            raise DiscordError("Discord created a channel but returned no channel ID.")
        return result

    def reorder(self, guild_id: str, channel_positions: list[dict[str, Any]]) -> None:
        self.transport.request(
            "PATCH", f"/guilds/{guild_id}/channels", token=self.token, body=channel_positions
        )
