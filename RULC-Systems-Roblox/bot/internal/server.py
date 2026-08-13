from __future__ import annotations

import logging

from aiohttp import web

from bot.db import Database

logger = logging.getLogger(__name__)


def _auth_ok(request: web.Request, secret: str) -> bool:
    if not secret:
        return False
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:] == secret
    return False


def create_app(db: Database, secret: str) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
            return web.json_response({"status": "ok", "service": "RULC-Systems-Roblox"})

    async def punishment_create(request: web.Request) -> web.Response:
        if not _auth_ok(request, secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        data = await request.json()
        pid = await db.create_punishment(
            guild_id=int(data["guild_id"]),
            cycle_case_id=str(data["cycle_case_id"]),
            cycle_snowflake=data.get("cycle_snowflake"),
            roblox_id=int(data["roblox_id"]),
            roblox_name=str(data["roblox_name"]),
            type_name=str(data["type"]),
            reason=str(data.get("reason", "")),
            staff_discord_id=data.get("staff_discord_id"),
            staff_name=data.get("staff_name"),
        )
        if pid is None:
            return web.json_response({"status": "duplicate"}, status=409)
        points = await db.sum_points(int(data["guild_id"]), int(data["roblox_id"]))
        return web.json_response({"status": "ok", "punishment_id": pid, "total_points": points})

    async def punishment_revoke(request: web.Request) -> web.Response:
        if not _auth_ok(request, secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        data = await request.json()
        ok = await db.revoke_punishment(
            guild_id=int(data["guild_id"]),
            cycle_case_id=str(data["cycle_case_id"]),
            revoked_by_discord_id=data.get("revoked_by_discord_id"),
            revoked_by_name=data.get("revoked_by_name"),
        )
        if not ok:
            return web.json_response({"status": "not_found"}, status=404)
        points = await db.sum_points(int(data["guild_id"]), int(data["roblox_id"]))
        return web.json_response({"status": "ok", "total_points": points})

    app.router.add_get("/health", health)
    app.router.add_post("/internal/punishment", punishment_create)
    app.router.add_post("/internal/punishment/revoke", punishment_revoke)
    return app


async def start_internal_server(
    db: Database,
    *,
    host: str,
    port: int,
    secret: str,
) -> web.AppRunner:
    app = create_app(db, secret)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Internal API listening on http://%s:%s", host, port)
    return runner
