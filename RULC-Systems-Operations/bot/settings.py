from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    discord_token: str
    dev_guild_ids: list[int]
    database_path: Path
    config_discord_ids: list[int]
    secrets_key: str | None = None
    project_root: Path = PROJECT_ROOT


def _parse_int_list(raw: str | None, *, name: str) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise RuntimeError(f"{name} must be comma-separated integers, got: {part!r}") from exc
    return ids


def resolve_database_path(raw: str | None = None) -> Path:
    db_path = Path(raw or os.getenv("DATABASE_PATH", "data/bot.db"))
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    return db_path


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")

    db_path = resolve_database_path()
    dev_guild_ids = _parse_int_list(os.getenv("DEV_GUILD_IDS"), name="DEV_GUILD_IDS")

    config_ids = _parse_int_list(os.getenv("CONFIG_DISCORD_IDS"), name="CONFIG_DISCORD_IDS")
    if not config_ids:
        config_ids = _parse_int_list(os.getenv("OWNER_DISCORD_IDS"), name="OWNER_DISCORD_IDS")

    return Settings(
        discord_token=token,
        dev_guild_ids=dev_guild_ids,
        database_path=db_path,
        config_discord_ids=config_ids,
        secrets_key=os.getenv("SECRETS_KEY", "").strip() or None,
        project_root=PROJECT_ROOT,
    )
