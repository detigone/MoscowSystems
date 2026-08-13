from __future__ import annotations

import asyncio
import logging

from bot.app import RoleSyncBot
from bot.settings import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("moscowsystems-bot")


async def main() -> None:
    settings = load_settings()
    bot = RoleSyncBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
