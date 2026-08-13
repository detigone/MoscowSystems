from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
import discord

from bot.db import Database

if TYPE_CHECKING:
    from bot.services.embeds import EmbedFactory

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(self, db: Database, embeds: EmbedFactory) -> None:
        self.db = db
        self.embeds = embeds
        self._session: aiohttp.ClientSession | None = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def relay_message(self, message: discord.Message) -> list[str]:
        if message.author.bot and message.webhook_id is None:
            return []
        if not message.guild:
            return []

        source = await self.db.get_broadcast_source_by_channel(message.channel.id)
        if not source:
            return []

        if source["require_role_id"]:
            if not isinstance(message.author, discord.Member):
                return []
            required = message.guild.get_role(source["require_role_id"])
            if required and required not in message.author.roles:
                return []

        targets = await self.db.get_broadcast_targets(source["id"])
        enabled_targets = [row for row in targets if row["enabled"]]
        if not enabled_targets:
            return []

        image_url = None
        attachment_urls = [att.url for att in message.attachments]
        if message.attachments:
            first = message.attachments[0]
            if first.content_type and first.content_type.startswith("image/"):
                image_url = first.url

        content = message.content
        if not content and message.embeds:
            content = message.embeds[0].description or message.embeds[0].title or ""

        payload = await self.embeds.broadcast_payload(
            message.guild,
            author_name=str(message.author),
            author_icon=getattr(message.author.display_avatar, "url", None),
            channel_name=message.channel.name,
            content=content or "",
            image_url=image_url,
            attachment_urls=attachment_urls if not image_url else None,
        )

        session = await self.get_session()
        results: list[str] = []

        for target in enabled_targets:
            try:
                async with session.post(target["webhook_url"], json=payload) as response:
                    if response.status >= 400:
                        body = await response.text()
                        results.append(f"{target['name']}: HTTP {response.status} — {body[:120]}")
                    else:
                        results.append(f"{target['name']}: OK")
            except aiohttp.ClientError as exc:
                results.append(f"{target['name']}: {exc}")
                logger.exception("Broadcast failed for target %s", target["name"])

        return results
