from __future__ import annotations

import re

DISCORD_WEBHOOK_PATTERN = re.compile(
    r"^https://(?:discord\.com|discordapp\.com)/api/webhooks/\d+/[\w-]+$",
    re.IGNORECASE,
)


def is_valid_discord_webhook(url: str) -> bool:
    cleaned = url.strip()
    return bool(DISCORD_WEBHOOK_PATTERN.match(cleaned))
