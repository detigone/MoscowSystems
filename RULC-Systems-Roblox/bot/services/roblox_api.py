from __future__ import annotations

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)


async def _get_json(session: aiohttp.ClientSession, url: str) -> dict | list | None:
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except aiohttp.ClientError:
        return None


async def fetch_roblox_user(session: aiohttp.ClientSession, username: str) -> dict | None:
    try:
        async with session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False},
        ) as resp:
            if resp.status == 404:
                return None
            if resp.status >= 400:
                logger.warning("Roblox username lookup HTTP %s for %s", resp.status, username)
                return None
            data = await resp.json()
            users = data.get("data") or []
            if not users:
                return None
            user = users[0]

        uid = user["id"]
        profile_task = _get_json(session, f"https://users.roblox.com/v1/users/{uid}")
        friends_task = _get_json(
            session, f"https://friends.roblox.com/v1/users/{uid}/friends/count"
        )
        groups_task = fetch_groups_count(session, uid)
        thumb_task = _get_json(
            session,
            "https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={uid}&size=150x150&format=Png&isCircular=false",
        )
        profile, friends, groups, thumb = await asyncio.gather(
            profile_task, friends_task, groups_task, thumb_task
        )

        if isinstance(profile, dict):
            user.update(profile)
            if profile.get("created"):
                user["created"] = profile["created"]
            if "isBanned" in profile:
                user["isBanned"] = profile["isBanned"]
        if isinstance(friends, dict):
            user["friendCount"] = friends.get("count")
        if groups is not None:
            user["groupCount"] = groups
        if isinstance(thumb, dict):
            items = thumb.get("data") or []
            if items:
                user["avatar_url"] = items[0].get("imageUrl")
        return user
    except aiohttp.ClientError:
        logger.exception("Roblox API request failed for %s", username)
        return None


async def fetch_groups_count(session: aiohttp.ClientSession, user_id: int) -> int | None:
    """Количество групп Roblox (до 100+, при обрезке возвращает минимум 100)."""
    try:
        url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles?limit=100"
        data = await _get_json(session, url)
        if not isinstance(data, dict):
            return None
        items = data.get("data") or []
        count = len(items)
        if data.get("nextPageCursor"):
            return max(count, 100)
        return count
    except aiohttp.ClientError:
        logger.debug("Groups count failed for user %s", user_id)
        return None


async def fetch_roblox_user_by_id(session: aiohttp.ClientSession, user_id: int) -> dict | None:
    try:
        profile, thumb = await asyncio.gather(
            _get_json(session, f"https://users.roblox.com/v1/users/{user_id}"),
            _get_json(
                session,
                "https://thumbnails.roblox.com/v1/users/avatar-headshot"
                f"?userIds={user_id}&size=150x150&format=Png&isCircular=false",
            ),
        )
        if not isinstance(profile, dict):
            return None
        user = profile
        if isinstance(thumb, dict):
            items = thumb.get("data") or []
            if items:
                user["avatar_url"] = items[0].get("imageUrl")
        return user
    except aiohttp.ClientError:
        logger.exception("Roblox API request failed for id %s", user_id)
        return None
