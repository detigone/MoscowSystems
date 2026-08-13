def _require_fields(data: dict, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if field not in data or data[field] in (None, ""):
            return field
    return None


def create_app(db: Database, secret: str) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "RULC-Systems-Roblox"})

    async def punishment_create(request: web.Request) -> web.Response:
        if not _auth_ok(request, secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            data = await request.json()
        except Exception:
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
                staff_discord_id=data.get("staff_discord_id"),
                staff_name=data.get("staff_name"),
            )
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
        except Exception:
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
                revoked_by_discord_id=data.get("revoked_by_discord_id"),
                revoked_by_name=data.get("revoked_by_name"),
            )
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        if not ok:
            return web.json_response({"status": "not_found"}, status=404)
        points = await db.sum_points(int(data["guild_id"]), int(data["roblox_id"]))
        return web.json_response({"status": "ok", "total_points": points})
