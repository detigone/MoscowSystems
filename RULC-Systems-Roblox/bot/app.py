from __future__ import annotations

import logging

import aiohttp
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

from bot.db import Database
from bot.internal.server import start_internal_server
from bot.settings import Settings

logger = logging.getLogger(__name__)

INTENTS = discord.Intents.default()
INTENTS.members = True

EXTENSIONS: tuple[str, ...] = (
    "bot.cogs.search",
    "bot.cogs.points",
    "bot.cogs.journal",
    "bot.cogs.stats",
    "bot.cogs.rules",
    "bot.cogs.help",
)


class RobloxBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self.settings = settings
        self.db = Database(str(settings.database_path))
        self._api_runner: web.AppRunner | None = None
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12),
            headers={"User-Agent": "RULC-Systems-Roblox/1.0"},
        )
        await self.db.connect()
        logger.info("Database: %s", self.settings.database_path)

        if not self.settings.internal_api_secret:
            logger.warning("INTERNAL_API_SECRET not set — CycleRM sync disabled")
        else:
            try:
                self._api_runner = await start_internal_server(
                    self.db,
                    host=self.settings.internal_api_host,
                    port=self.settings.internal_api_port,
                    secret=self.settings.internal_api_secret,
                )
            except OSError as exc:
                logger.critical(
                    "Could not bind internal API on %s:%s — %s",
                    self.settings.internal_api_host,
                    self.settings.internal_api_port,
                    exc,
                )
                raise

        for extension in EXTENSIONS:
            await self.load_extension(extension)

        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ) -> None:
            logger.exception("Slash command error: %s", error)
            msg = "Произошла ошибка при выполнении команды."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        if self.settings.dev_guild_ids:
            for gid in self.settings.dev_guild_ids:
                self.tree.copy_global_to(guild=discord.Object(id=gid))
                await self.tree.sync(guild=discord.Object(id=gid))
            logger.info("Slash commands synced to dev guilds: %s", self.settings.dev_guild_ids)
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally")

    async def on_ready(self) -> None:
        logger.info(
            "RU:LC Roblox online as %s (%s) | guilds: %s | API: %s",
            self.user,
            self.user.id if self.user else "?",
            len(self.guilds),
            "enabled" if self._api_runner else "disabled",
        )

    async def close(self) -> None:
        if self._api_runner:
            await self._api_runner.cleanup()
        if self.http_session:
            await self.http_session.close()
        await self.db.close()
        await super().close()
