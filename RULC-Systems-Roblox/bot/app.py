from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.db import Database
from bot.internal.server import start_internal_server
from bot.settings import Settings

logger = logging.getLogger(__name__)

INTENTS = discord.Intents.default()
INTENTS.members = True


class RobloxBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self.settings = settings
        self.db = Database(str(settings.database_path))
        self._api_runner = None

    async def setup_hook(self) -> None:
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        await self.db.connect()
        logger.info("Database: %s", self.settings.database_path)

        if not self.settings.internal_api_secret:
            logger.warning("INTERNAL_API_SECRET not set — CycleRM sync disabled")
        else:
            self._api_runner = await start_internal_server(
                self.db,
                host=self.settings.internal_api_host,
                port=self.settings.internal_api_port,
                secret=self.settings.internal_api_secret,
            )

        await self.load_extension("bot.cogs.search")

        if self.settings.dev_guild_ids:
            for gid in self.settings.dev_guild_ids:
                self.tree.copy_global_to(guild=discord.Object(id=gid))
                await self.tree.sync(guild=discord.Object(id=gid))
        else:
            await self.tree.sync()

    async def close(self) -> None:
        if self._api_runner:
            await self._api_runner.cleanup()
        await self.db.close()
        await super().close()
