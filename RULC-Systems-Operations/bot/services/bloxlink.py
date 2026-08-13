from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

BLOXLINK_BASE = "https://api.blox.link/v4/public"
ROBLOX_USERS_API = "https://users.roblox.com/v1/users"


@dataclass(frozen=True)
class BloxlinkAccount:
    roblox_id: int
    username: str


class BloxlinkService:
    """Resolves Discord users to Roblox accounts via the Bloxlink guild API."""

    def __init__(self, api_key: str, guild_id: int) -> None:
        self.api_key = api_key
        self.guild_id = guild_id
        self._session: aiohttp.ClientSession | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.guild_id)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": self.api_key},
                timeout=aiohttp.ClientTimeout(total=15),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_roblox_account(self, discord_user_id: int) -> BloxlinkAccount | None:
        if not self.configured:
            logger.warning("Bloxlink is not configured")
            return None

        url = f"{BLOXLINK_BASE}/guilds/{self.guild_id}/discord-to-roblox/{discord_user_id}"
        session = await self._get_session()

        try:
            async with session.get(url) as response:
                if response.status == 404:
                    return None
                if response.status >= 400:
                    body = await response.text()
                    logger.error("Bloxlink API error %s: %s", response.status, body[:200])
                    return None

                data = await response.json()
        except aiohttp.ClientError:
            logger.exception("Bloxlink request failed for user %s", discord_user_id)
            return None

        roblox_id = data.get("robloxID") or data.get("robloxId")
        if not roblox_id:
            return None

        roblox_id = int(roblox_id)
        username = self._extract_username(data)
        if not username:
            username = await self._fetch_roblox_username(roblox_id)
        if not username:
            return None

        return BloxlinkAccount(roblox_id=roblox_id, username=username)

    def _extract_username(self, data: dict) -> str | None:
        resolved = data.get("resolved") or {}
        roblox = resolved.get("roblox") or {}
        for key in ("name", "displayName"):
            value = roblox.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    async def _fetch_roblox_username(self, roblox_id: int) -> str | None:
        session = await self._get_session()
        try:
            async with session.get(f"{ROBLOX_USERS_API}/{roblox_id}") as response:
                if response.status >= 400:
                    return None
                data = await response.json()
        except aiohttp.ClientError:
            logger.exception("Roblox username lookup failed for %s", roblox_id)
            return None

        name = data.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
