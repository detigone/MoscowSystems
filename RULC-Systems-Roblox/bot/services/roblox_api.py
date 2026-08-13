from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)


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

        async with session.get(f"https://users.roblox.com/v1/users/{user['id']}") as resp:
            if resp.status == 200:
                profile = await resp.json()
                user.update(profile)
                created = profile.get("created")
                if created:
                    user["created"] = created

        async with session.get(
            f"https://friends.roblox.com/v1/users/{user['id']}/friends/count"
        ) as resp:
            if resp.status == 200:
                user["friendCount"] = (await resp.json()).get("count")

        async with session.get(
            "https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={user['id']}&size=150x150&format=Png&isCircular=false"
        ) as resp:
            if resp.status == 200:
                items = (await resp.json()).get("data") or []
                if items:
                    user["avatar_url"] = items[0].get("imageUrl")
        return user
    except aiohttp.ClientError:
        logger.exception("Roblox API request failed for %s", username)
        return None


async def fetch_roblox_user_by_id(session: aiohttp.ClientSession, user_id: int) -> dict | None:
    try:
        async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
            if resp.status != 200:
                return None
            user = await resp.json()

        async with session.get(
            "https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={user_id}&size=150x150&format=Png&isCircular=false"
        ) as resp:
            if resp.status == 200:
                items = (await resp.json()).get("data") or []
                if items:
                    user["avatar_url"] = items[0].get("imageUrl")
        return user
    except aiohttp.ClientError:
        logger.exception("Roblox API request failed for id %s", user_id)
        return None
