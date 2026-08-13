PUNISHMENT_TYPE_POINTS = {
    "warning": 1,
    "kick": 3,
    "ban": 10,
    "bolo": 5,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS punishment_type_points (
    guild_id INTEGER NOT NULL,
    type_key TEXT NOT NULL,
    points INTEGER NOT NULL,
    PRIMARY KEY (guild_id, type_key)
);

CREATE TABLE IF NOT EXISTS punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    cycle_case_id TEXT NOT NULL UNIQUE,
    cycle_snowflake INTEGER,
    roblox_id INTEGER NOT NULL,
    roblox_name TEXT NOT NULL,
    type_key TEXT NOT NULL,
    reason TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    staff_discord_id INTEGER,
    staff_name TEXT,
    revoked INTEGER NOT NULL DEFAULT 0,
    revoked_at TEXT,
    revoked_by_discord_id INTEGER,
    revoked_by_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS points_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    roblox_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    staff_discord_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recent_moderated (
    guild_id INTEGER NOT NULL,
    roblox_name TEXT NOT NULL,
    roblox_id INTEGER NOT NULL,
    moderated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, roblox_name)
);

CREATE INDEX IF NOT EXISTS idx_punishments_guild_roblox
    ON punishments (guild_id, roblox_id);

CREATE INDEX IF NOT EXISTS idx_ledger_guild_roblox
    ON points_ledger (guild_id, roblox_id);
"""
