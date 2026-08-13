from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_BLOXLINK_BASE = "https://api.blox.link/v4/public"


class BloxlinkClient:
    """Bloxlink API v4 — привязка Discord ↔ Roblox."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key.strip()

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def _request(self, url: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            async with self._session.get(
                url,
                headers={"Authorization": self._api_key},
            ) as resp:
                if resp.status == 404:
                    return None
                if resp.status >= 400:
                    logger.debug("Bloxlink HTTP %s for %s", resp.status, url)
                    return None
                data = await resp.json()
                if not isinstance(data, dict):
                    return None
                if data.get("error"):
                    return None
                return data
        except aiohttp.ClientError:
            logger.debug("Bloxlink request failed: %s", url, exc_info=True)
            return None

    async def discord_to_roblox(
        self,
        discord_id: int,
        *,
        guild_id: int | None = None,
    ) -> int | None:
        if guild_id is not None:
            url = f"{_BLOXLINK_BASE}/guilds/{guild_id}/discord-to-roblox/{discord_id}"
        else:
            url = f"{_BLOXLINK_BASE}/discord-to-roblox/{discord_id}"
        data = await self._request(url)
        if not data:
            return None
        raw = data.get("robloxID") or data.get("robloxId")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def roblox_to_discord_ids(
        self,
        roblox_id: int,
        *,
        guild_id: int | None = None,
    ) -> list[int]:
        if guild_id is not None:
            url = f"{_BLOXLINK_BASE}/guilds/{guild_id}/roblox-to-discord/{roblox_id}"
        else:
            url = f"{_BLOXLINK_BASE}/roblox-to-discord/{roblox_id}"
        data = await self._request(url)
        if not data:
            return []
        raw_ids = data.get("discordIDs") or data.get("discordIds") or []
        ids: list[int] = []
        for item in raw_ids:
            try:
                ids.append(int(item))
            except (TypeError, ValueError):
                continue
        return ids

    async def resolve_guild_member(
        self,
        guild: Any,
        roblox_id: int,
    ) -> tuple[Any | None, str | None, int | None]:
        """Найти участника сервера по Roblox ID через Bloxlink."""
        import discord

        if not isinstance(guild, discord.Guild):
            return None, None, None

        for guild_scoped in (True, False):
            ids = await self.roblox_to_discord_ids(
                roblox_id,
                guild_id=guild.id if guild_scoped else None,
            )
            if not ids:
                continue
            for discord_id in ids:
                member = guild.get_member(discord_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(discord_id)
                    except discord.NotFound:
                        member = None
                if member is not None:
                    return member, "bloxlink", None
            return None, "bloxlink_offserver", ids[0]
        return None, None, None
