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
    admin_discord_ids: list[int]
    database_path: Path
    internal_api_host: str
    internal_api_port: int
    internal_api_secret: str


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


def _parse_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"INTERNAL_API_PORT must be an integer, got: {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(f"INTERNAL_API_PORT must be between 1 and 65535, got: {port}")
    return port


def _parse_internal_host(raw: str) -> str:
    host = raw.strip().lower()
    if host in {"0.0.0.0", "::", "::0", ""}:
        raise RuntimeError(
            "INTERNAL_API_HOST must be 127.0.0.1 or localhost (binding to all interfaces is disabled)"
        )
    return raw.strip()


def resolve_database_path() -> Path:
    raw = Path(os.getenv("DATABASE_PATH", "data/roblox.db"))
    if not raw.is_absolute():
        raw = PROJECT_ROOT / raw
    return raw


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")

    host = _parse_internal_host(os.getenv("INTERNAL_API_HOST", "127.0.0.1"))
    db_path = resolve_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        discord_token=token,
        dev_guild_ids=_parse_int_list(os.getenv("DEV_GUILD_IDS"), name="DEV_GUILD_IDS"),
        admin_discord_ids=_parse_int_list(os.getenv("ADMIN_DISCORD_IDS"), name="ADMIN_DISCORD_IDS"),
        database_path=db_path,
        internal_api_host=host,
        internal_api_port=_parse_port(os.getenv("INTERNAL_API_PORT", "8081")),
        internal_api_secret=os.getenv("INTERNAL_API_SECRET", "").strip(),
    )
