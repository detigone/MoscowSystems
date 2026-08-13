SCHEMA = """
CREATE TABLE IF NOT EXISTS point_rules (
    guild_id INTEGER NOT NULL,
    type_key TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, type_key)
);

CREATE TABLE IF NOT EXISTS punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    cycle_case_id TEXT NOT NULL,
    cycle_snowflake TEXT,
    roblox_id INTEGER NOT NULL,
    roblox_name TEXT NOT NULL,
    type_key TEXT NOT NULL,
    reason TEXT,
    description TEXT,
    points INTEGER NOT NULL,
    staff_discord_id INTEGER,
    staff_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    revoked_at TEXT,
    revoked_by_discord_id INTEGER,
    revoked_by_name TEXT,
    UNIQUE (guild_id, cycle_case_id)
);

CREATE INDEX IF NOT EXISTS idx_punishments_guild_roblox
    ON punishments (guild_id, roblox_id);
CREATE INDEX IF NOT EXISTS idx_punishments_guild_roblox_active
    ON punishments (guild_id, roblox_id, revoked_at);
CREATE INDEX IF NOT EXISTS idx_punishments_guild_name
    ON punishments (guild_id, roblox_name COLLATE NOCASE);
"""

DEFAULT_POINT_RULES = (
    ("warning", 1),
    ("kick", 3),
    ("ban", 10),
    ("tempban", 10),
    ("bolo", 5),
    ("demorgan", 5),
    ("jail", 5),
    ("note", 0),
)
