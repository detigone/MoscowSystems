from __future__ import annotations

import pytest

GUILD_ID = 42
USER_ID = 100


@pytest.mark.asyncio
async def test_mod_call_config_defaults(db):
    config = await db.get_mod_call_config(GUILD_ID)
    assert int(config["cooldown_seconds"]) == 300
    assert int(config["enabled"]) == 1
    assert config["channel_id"] is None


@pytest.mark.asyncio
async def test_mod_call_roles_and_cooldown(db):
    await db.update_mod_call_config(GUILD_ID, channel_id=999)
    await db.add_mod_call_role(GUILD_ID, 555)
    roles = await db.list_mod_call_roles(GUILD_ID)
    assert 555 in roles

    await db.touch_mod_call_cooldown(GUILD_ID, USER_ID)
    remaining = await db.mod_call_cooldown_remaining(GUILD_ID, USER_ID)
    assert remaining > 0

    await db.update_mod_call_config(GUILD_ID, cooldown_seconds=0)
    assert await db.mod_call_cooldown_remaining(GUILD_ID, USER_ID) == 0
