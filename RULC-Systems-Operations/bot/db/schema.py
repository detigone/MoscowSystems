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
    embed_color TEXT NOT NULL DEFAULT '#4FC3F7'
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

CREATE INDEX IF NOT EXISTS idx_erlc_log_events_guild_type_ts
    ON erlc_log_events (guild_id, event_type, event_ts);
CREATE INDEX IF NOT EXISTS idx_erlc_player_snapshots_guild_time
    ON erlc_player_snapshots (guild_id, recorded_at);

CREATE TABLE IF NOT EXISTS guild_embed_settings (
    guild_id INTEGER PRIMARY KEY,
    brand_name TEXT NOT NULL DEFAULT 'RU:LC Systems',
    footer_text TEXT NOT NULL DEFAULT '',
    thumbnail_url TEXT,
    color_primary TEXT NOT NULL DEFAULT '#2B2D31',
    color_success TEXT NOT NULL DEFAULT '#57F287',
    color_warning TEXT NOT NULL DEFAULT '#FEE75C',
    color_danger TEXT NOT NULL DEFAULT '#ED4245',
    color_info TEXT NOT NULL DEFAULT '#00A8FC',
    show_timestamp INTEGER NOT NULL DEFAULT 0,
    use_guild_icon INTEGER NOT NULL DEFAULT 0,
    players_per_field INTEGER NOT NULL DEFAULT 10
);

CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id INTEGER PRIMARY KEY,
    discord_category_id INTEGER,
    log_channel_id INTEGER,
    panel_channel_id INTEGER,
    panel_message_id INTEGER,
    name_template TEXT NOT NULL DEFAULT '・{step}・{category}-{number}',
    max_open_per_user INTEGER NOT NULL DEFAULT 3,
    counter INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ticket_staff_roles (
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS ticket_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL DEFAULT '📩',
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    category_id INTEGER,
    channel_id INTEGER NOT NULL UNIQUE,
    opener_id INTEGER NOT NULL,
    opener_name TEXT NOT NULL,
    claimed_by_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    subject TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    closed_by_id INTEGER,
    close_reason TEXT,
    transcript TEXT,
    ticket_number INTEGER,
    FOREIGN KEY (category_id) REFERENCES ticket_categories(id)
);

CREATE INDEX IF NOT EXISTS idx_tickets_guild_opener_status
    ON tickets (guild_id, opener_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_guild_status
    ON tickets (guild_id, status);
"""
