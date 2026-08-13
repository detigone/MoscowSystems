from __future__ import annotations

import logging

from bot.db import Database

logger = logging.getLogger(__name__)


class ErlcService:
    """ER:LC API: сервер, игроки, логи и команды."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def _client(self, guild_id: int):
        config = await self.db.get_erlc_server(guild_id)
        if not config:
            return None, None
        try:
            from erlc_api import AsyncClient
        except ImportError as exc:
            raise RuntimeError("Пакет erlc-api.py не установлен") from exc
        return config, AsyncClient(config["server_key"])

    async def fetch_server_info_with_key(self, server_key: str) -> dict:
        try:
            from erlc_api import AsyncClient
        except ImportError as exc:
            raise RuntimeError("Пакет erlc-api.py не установлен") from exc

        async with AsyncClient(server_key) as client:
            server = await client.server()
            return {
                "name": server.name,
                "players": server.current_players,
                "max_players": server.max_players,
                "join_code": getattr(server, "join_code", None),
            }

    async def fetch_server_info(self, guild_id: int) -> dict:
        config = await self.db.get_erlc_server(guild_id)
        if not config:
            raise RuntimeError("ER:LC сервер не настроен")
        return await self.fetch_server_info_with_key(config["server_key"])

    async def get_player_count(self, guild_id: int) -> int | None:
        config, client_cls = await self._client(guild_id)
        if not config:
            return None
        async with client_cls as client:
            server = await client.server()
            return int(server.current_players)

    async def get_players(self, guild_id: int) -> list:
        config, client_cls = await self._client(guild_id)
        if not config:
            raise RuntimeError("ER:LC не настроен")
        async with client_cls as client:
            return await client.players()

    async def fetch_logs(self, guild_id: int, log_type: str):
        config, client_cls = await self._client(guild_id)
        if not config:
            raise RuntimeError("ER:LC не настроен")
        async with client_cls as client:
            return await client.logs(log_type)

    async def run_command(self, guild_id: int, command: str) -> str:
        config, client_cls = await self._client(guild_id)
        if not config:
            raise RuntimeError("ER:LC сервер не настроен")

        try:
            from erlc_api import AsyncClient, CommandPolicy
        except ImportError as exc:
            raise RuntimeError("Пакет erlc-api.py не установлен") from exc

        policy = CommandPolicy(allowed={"h", "pm", "kick", "ban", "m"}, max_length=200)
        async with AsyncClient(config["server_key"]) as client:
            await client.command(command, policy=policy)
        return f"Команда выполнена: `{command}`"
