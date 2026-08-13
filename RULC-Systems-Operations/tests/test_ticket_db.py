from __future__ import annotations

import asyncio

import pytest


GUILD_ID = 9001
CHANNEL_ID = 8001
OPENER_ID = 7001


@pytest.mark.asyncio
async def test_ticket_config_automation_defaults(db):
    config = await db.get_ticket_config(GUILD_ID)
    assert int(config["idle_close_hours"]) == 0
    assert int(config["remind_unclaimed_hours"]) == 0


@pytest.mark.asyncio
async def test_update_automation_settings(db):
    await db.update_ticket_config(
        GUILD_ID,
        idle_close_hours=48,
        remind_unclaimed_hours=6,
    )
    config = await db.get_ticket_config(GUILD_ID)
    assert int(config["idle_close_hours"]) == 48
    assert int(config["remind_unclaimed_hours"]) == 6


@pytest.mark.asyncio
async def test_touch_ticket_activity_only_open(db):
    ticket_id = await db.create_ticket(
        guild_id=GUILD_ID,
        category_id=None,
        channel_id=CHANNEL_ID,
        opener_id=OPENER_ID,
        opener_name="user",
    )
    row = await db.get_ticket_by_channel(CHANNEL_ID)
    assert row is not None
    first_activity = row["last_activity_at"]

    await asyncio.sleep(1.1)
    await db.touch_ticket_activity(CHANNEL_ID)
    row = await db.get_ticket_by_channel(CHANNEL_ID)
    assert row["last_activity_at"] != first_activity

    await db.close_ticket(ticket_id, closed_by_id=1, reason="test")
    before = row["last_activity_at"]
    await db.touch_ticket_activity(CHANNEL_ID)
    row = await db.get_ticket_by_channel(CHANNEL_ID)
    assert row["last_activity_at"] == before


@pytest.mark.asyncio
async def test_mark_staff_ping(db):
    ticket_id = await db.create_ticket(
        guild_id=GUILD_ID,
        category_id=None,
        channel_id=CHANNEL_ID + 1,
        opener_id=OPENER_ID,
        opener_name="user",
    )
    await db.mark_staff_ping(ticket_id)
    row = await db.get_ticket_by_channel(CHANNEL_ID + 1)
    assert row["last_staff_ping_at"] is not None


@pytest.mark.asyncio
async def test_guilds_with_open_tickets(db):
    await db.create_ticket(
        guild_id=GUILD_ID,
        category_id=None,
        channel_id=CHANNEL_ID + 2,
        opener_id=OPENER_ID,
        opener_name="user",
    )
    guilds = await db.guilds_with_open_tickets()
    assert GUILD_ID in guilds
