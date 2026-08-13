from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    discord_token: str
    dev_guild_ids: list[int]
    database_path: Path
    internal_api_host: str
    internal_api_port: int
    internal_api_secret: str
    bloxlink_api_key: str
    bloxlink_guild_id: int


def _parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def resolve_database_path() -> Path:
    raw = Path(os.getenv("DATABASE_PATH", "data/roblox.db"))
    if not raw.is_absolute():
        raw = PROJECT_ROOT / raw
    return raw


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")

    dev = _parse_int_list(os.getenv("DEV_GUILD_IDS"))
    bloxlink_guild_raw = os.getenv("BLOXLINK_GUILD_ID", "").strip()
    if bloxlink_guild_raw:
        bloxlink_guild_id = int(bloxlink_guild_raw)
    elif dev:
        bloxlink_guild_id = dev[0]
    else:
        bloxlink_guild_id = 0

    return Settings(
        discord_token=token,
        dev_guild_ids=dev,
        database_path=resolve_database_path(),
        internal_api_host=os.getenv("INTERNAL_API_HOST", "127.0.0.1"),
        internal_api_port=int(os.getenv("INTERNAL_API_PORT", "8081")),
        internal_api_secret=os.getenv("INTERNAL_API_SECRET", "").strip(),
        bloxlink_api_key=os.getenv("BLOXLINK_API_KEY", "").strip(),
        bloxlink_guild_id=bloxlink_guild_id,
    )
