from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.db import Database
from bot.services.autorole import AutoroleService
from bot.services.broadcast import BroadcastService
from bot.services.conditional_roles import ConditionalRoleService
from bot.services.embeds import EmbedFactory
from bot.services.erlc import ErlcService
from bot.services.erlc_stats import ErlcStatsService
from bot.services.role_sync import RoleSyncService
from bot.settings import Settings

logger = logging.getLogger(__name__)

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.guilds = True
INTENTS.message_content = True

EXTENSIONS: tuple[str, ...] = (
    "bot.cogs.config",
    "bot.cogs.erlc",
    "bot.cogs.events.sync",
    "bot.cogs.events.guild",
    "bot.cogs.events.broadcast",
    "bot.cogs.tasks",
)


class RoleSyncBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self.settings = settings
        self.db = Database(str(settings.database_path))
        self.embeds: EmbedFactory
        self.role_sync: RoleSyncService
        self.erlc: ErlcService
        self.erlc_stats: ErlcStatsService
        self.autorole: AutoroleService
        self.conditional_roles: ConditionalRoleService
        self.broadcast: BroadcastService

    async def setup_hook(self) -> None:
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        await self.db.connect()
        logger.info("Local database: %s", self.settings.database_path)

        self.embeds = EmbedFactory(self.db)
        self.role_sync = RoleSyncService(self.db, self)
        self.erlc = ErlcService(self.db)
        self.erlc_stats = ErlcStatsService(self.db, self.erlc, self.embeds)
        self.autorole = AutoroleService(self.db)
        self.conditional_roles = ConditionalRoleService(self.db)
        self.broadcast = BroadcastService(self.db, self.embeds)

        for extension in EXTENSIONS:
            await self.load_extension(extension)

        if self.settings.dev_guild_ids:
            for guild_id in self.settings.dev_guild_ids:
                self.tree.copy_global_to(guild=discord.Object(id=guild_id))
                await self.tree.sync(guild=discord.Object(id=guild_id))
            logger.info("Slash commands synced to dev guilds: %s", self.settings.dev_guild_ids)
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally")

    async def close(self) -> None:
        await self.broadcast.close()
        await self.db.close()
        await super().close()
