"""Sync punishments to RU:LC Systems Roblox (points live there)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from decouple import config

logger = logging.getLogger(__name__)

try:
    RULC_ROBLOX_URL = config("RULC_ROBLOX_URL", default="").rstrip("/")
    RULC_ROBLOX_SECRET = config("RULC_ROBLOX_SECRET", default="")
except Exception:
    RULC_ROBLOX_URL = ""
    RULC_ROBLOX_SECRET = ""


def configured() -> bool:
    return bool(RULC_ROBLOX_URL and RULC_ROBLOX_SECRET)


async def _post(path: str, payload: dict[str, Any]) -> bool:
    if not configured():
        logger.debug("RU:LC Roblox sync skipped (RULC_ROBLOX_URL/SECRET not set)")
        return False

    url = f"{RULC_ROBLOX_URL}{path}"
    headers = {
        "Authorization": f"Bearer {RULC_ROBLOX_SECRET}",
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("RU:LC Roblox sync failed %s: %s", resp.status, body[:300])
                    return False
                logger.info("RU:LC Roblox sync OK: %s", path)
                return True
    except aiohttp.ClientError:
        logger.exception("RU:LC Roblox sync request failed")
        return False


async def sync_punishment_created(warning) -> bool:
    """Push new punishment to Roblox bot (points assigned there)."""
    payload: dict[str, Any] = {
        "guild_id": warning.guild_id,
        "cycle_case_id": str(warning.id),
        "cycle_snowflake": warning.snowflake,
        "roblox_id": warning.user_id,
        "roblox_name": warning.username,
        "type": warning.warning_type,
        "reason": warning.reason,
        "staff_discord_id": warning.moderator_id,
        "staff_name": warning.moderator_name,
        "created_at": int(warning.time_epoch),
    }
    if warning.until_epoch:
        from datetime import datetime, timezone

        payload["expires_at"] = datetime.fromtimestamp(
            int(warning.until_epoch), tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
    return await _post("/internal/punishment", payload)


async def sync_punishment_revoked(warning, manager: Any) -> bool:
    """Tell Roblox bot to revoke punishment and adjust points."""
    return await _post(
        "/internal/punishment/revoke",
        {
            "guild_id": warning.guild_id,
            "cycle_case_id": str(warning.id),
            "cycle_snowflake": warning.snowflake,
            "roblox_id": warning.user_id,
            "roblox_name": warning.username,
            "type": warning.warning_type,
            "revoked_by_discord_id": manager.id,
            "revoked_by_name": str(manager),
        },
    )
