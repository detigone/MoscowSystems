"""Environment helpers for CUSTOM self-host and MongoDB task scoping."""

from __future__ import annotations

from decouple import config

_environment = config("ENVIRONMENT", default="DEVELOPMENT").upper()
_custom_guild_id: int | None = None


def environment() -> str:
    return _environment


def custom_guild_id() -> int:
    global _custom_guild_id
    if _custom_guild_id is None:
        raw = config("CUSTOM_GUILD_ID", default="0").strip()
        try:
            _custom_guild_id = int(raw or "0")
        except ValueError:
            _custom_guild_id = 0
    return _custom_guild_id


def is_custom() -> bool:
    return _environment == "CUSTOM"


def custom_guild_filter_id() -> dict:
    """Filter for collections keyed by guild snowflake in `_id`."""
    if is_custom() and custom_guild_id():
        return {"_id": custom_guild_id()}
    return {}


def custom_guild_filter_guild() -> dict:
    """Filter for collections that store guild id in `guild` field."""
    if is_custom() and custom_guild_id():
        return {"guild": custom_guild_id()}
    return {}


def custom_guild_filter_guild_id() -> dict:
    """Filter for collections that store guild id in `Guild` field."""
    if is_custom() and custom_guild_id():
        return {"Guild": custom_guild_id()}
    return {}


def is_allowed_custom_guild(guild_id: int) -> bool:
    cid = custom_guild_id()
    if not is_custom() or not cid:
        return True
    return guild_id == cid
