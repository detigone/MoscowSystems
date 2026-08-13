SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_group_guilds (
    group_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, guild_id),
    FOREIGN KEY (group_id) REFERENCES sync_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS synced_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    role_name TEXT NOT NULL,
    UNIQUE (group_id, role_name),
    FOREIGN KEY (group_id) REFERENCES sync_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS role_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    source_guild_id INTEGER NOT NULL,
    source_role_id INTEGER NOT NULL,
    target_guild_id INTEGER NOT NULL,
    target_role_id INTEGER NOT NULL,
    UNIQUE (group_id, source_guild_id, source_role_id, target_guild_id),
    FOREIGN KEY (group_id) REFERENCES sync_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS erlc_servers (
    guild_id INTEGER PRIMARY KEY,
    server_key TEXT NOT NULL,
    server_name TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_registry (
    guild_id INTEGER PRIMARY KEY,
    guild_name TEXT NOT NULL,
    icon_url TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_autoroles (
    guild_id INTEGER PRIMARY KEY,
    member_role_id INTEGER,
    bot_role_id INTEGER,
    member_enabled INTEGER NOT NULL DEFAULT 1,
    bot_enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS conditional_role_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    target_role_id INTEGER NOT NULL,
    remove_on_loss INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conditional_role_triggers (
    rule_id INTEGER NOT NULL,
    trigger_role_id INTEGER NOT NULL,
    PRIMARY KEY (rule_id, trigger_role_id),
    FOREIGN KEY (rule_id) REFERENCES conditional_role_rules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS broadcast_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_guild_id INTEGER NOT NULL,
    source_channel_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT 'Рассылка',
    enabled INTEGER NOT NULL DEFAULT 1,
    require_role_id INTEGER,
    embed_color TEXT NOT NULL DEFAULT '#5865F2'
);

CREATE TABLE IF NOT EXISTS broadcast_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    webhook_url TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (source_id) REFERENCES broadcast_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voice_player_counters (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    name_template TEXT NOT NULL DEFAULT '╭・📡 ・Игроков на сервере: {count}',
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS erlc_log_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    player_name TEXT,
    player_id TEXT,
    extra_a TEXT,
    extra_b TEXT,
    event_ts INTEGER NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS erlc_player_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    player_count INTEGER NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_embed_settings (
    guild_id INTEGER PRIMARY KEY,
    brand_name TEXT NOT NULL DEFAULT 'MoscowSystems',
    footer_text TEXT NOT NULL DEFAULT 'MoscowSystems • ER:LC Network',
    thumbnail_url TEXT,
    color_primary TEXT NOT NULL DEFAULT '#5865F2',
    color_success TEXT NOT NULL DEFAULT '#57F287',
    color_warning TEXT NOT NULL DEFAULT '#FEE75C',
    color_danger TEXT NOT NULL DEFAULT '#ED4245',
    color_info TEXT NOT NULL DEFAULT '#00A8FC',
    show_timestamp INTEGER NOT NULL DEFAULT 1,
    use_guild_icon INTEGER NOT NULL DEFAULT 1,
    players_per_field INTEGER NOT NULL DEFAULT 10
);
"""
