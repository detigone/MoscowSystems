from __future__ import annotations

import json
import logging
import secrets

from aiohttp import web

from bot.db import Database

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024


@web.middleware
async def auth_log_middleware(request: web.Request, handler):
    if request.path.startswith("/internal/"):
        secret = request.app["secret"]
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not secrets.compare_digest(
            header[7:], secret
        ):
            logger.warning(
                "Internal API unauthorized %s from %s",
                request.path,
                request.remote,
            )
    return await handler(request)


def _auth_ok(request: web.Request, secret: str) -> bool:
    if not secret:
        return False
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return False
    token = header[7:]
    return secrets.compare_digest(token, secret)


def _require_fields(data: dict, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if field not in data or data[field] in (None, ""):
            return field
    return None


def _optional_int(value: object, field: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_{field}") from exc


def create_app(db: Database, secret: str) -> web.Application:
    app = web.Application(
        middlewares=[auth_log_middleware],
        client_max_size=MAX_BODY_BYTES,
    )
    app["db"] = db
    app["secret"] = secret

    async def health(_request: web.Request) -> web.Response:
        try:
            assert db.conn is not None
            await db.conn.execute("SELECT 1")
            return web.json_response({"status": "ok", "db": "ok"})
        except Exception:
            logger.exception("Health check DB ping failed")
            return web.json_response({"status": "degraded", "db": "error"}, status=503)

    async def punishment_create(request: web.Request) -> web.Response:
        if not _auth_ok(request, secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)
        if not isinstance(data, dict):
            return web.json_response({"error": "invalid_json"}, status=400)

        missing = _require_fields(
            data,
            ("guild_id", "cycle_case_id", "roblox_id", "roblox_name", "type"),
        )
        if missing:
            return web.json_response({"error": f"missing_{missing}"}, status=400)
        try:
            pid = await db.create_punishment(
                guild_id=int(data["guild_id"]),
                cycle_case_id=str(data["cycle_case_id"]),
                cycle_snowflake=data.get("cycle_snowflake"),
                roblox_id=int(data["roblox_id"]),
                roblox_name=str(data["roblox_name"]),
                type_name=str(data["type"]),
                reason=str(data.get("reason", "")),
                description=data.get("description"),
                staff_discord_id=_optional_int(data.get("staff_discord_id"), "staff_discord_id"),
                staff_name=data.get("staff_name"),
                created_at_epoch=_optional_int(data.get("created_at"), "created_at"),
                expires_at=data.get("expires_at"),
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        if pid is None:
            return web.json_response({"status": "duplicate"}, status=409)
        points = await db.sum_points(int(data["guild_id"]), int(data["roblox_id"]))
        return web.json_response({"status": "ok", "punishment_id": pid, "total_points": points})

    async def punishment_revoke(request: web.Request) -> web.Response:
        if not _auth_ok(request, secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)
        if not isinstance(data, dict):
            return web.json_response({"error": "invalid_json"}, status=400)

        missing = _require_fields(
            data,
            ("guild_id", "cycle_case_id", "roblox_id"),
        )
        if missing:
            return web.json_response({"error": f"missing_{missing}"}, status=400)
        try:
            ok = await db.revoke_punishment(
                guild_id=int(data["guild_id"]),
                cycle_case_id=str(data["cycle_case_id"]),
                revoked_by_discord_id=_optional_int(
                    data.get("revoked_by_discord_id"), "revoked_by_discord_id"
                ),
                revoked_by_name=data.get("revoked_by_name"),
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
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
