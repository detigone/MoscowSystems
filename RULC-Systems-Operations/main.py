from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parent.parent / "shared"
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from bot.app import RoleSyncBot
from bot.settings import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("rulc-operations")


def main() -> None:
    try:
        settings = load_settings()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    bot = RoleSyncBot(settings)
    try:
        asyncio.run(bot.start(settings.discord_token))
    except KeyboardInterrupt:
        logger.info("Shutting down…")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
