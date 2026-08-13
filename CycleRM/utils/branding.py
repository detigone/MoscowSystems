"""CycleRM branding — имя бота и emoji для UI."""

from decouple import config

BOT_NAME = "CycleRM"
NETWORK_NAME = "RU:LC Systems"

# Основные цвета embed (см. utils/constants.py)
BRAND_COLOR = 0x4FC3F7
BRAND_COLOR_DARK = 0x0288D1


def _emoji(env_key: str, fallback: str) -> str:
    """Custom Discord emoji (<:name:id>) or unicode fallback."""
    raw = config(env_key, default="").strip()
    return raw if raw else fallback


# Unicode по умолчанию — работают на любом сервере.
# Свои emoji: загрузи PNG/GIF в Discord → Server Settings → Emoji → скопируй <:Name:ID> в .env
EMOJI_SUCCESS = _emoji("EMOJI_SUCCESS", "✅")
EMOJI_ERROR = _emoji("EMOJI_ERROR", "❌")
EMOJI_PENDING = _emoji("EMOJI_PENDING", "⏳")
EMOJI_ALERT = _emoji("EMOJI_ALERT", "⚠️")
EMOJI_LIST = _emoji("EMOJI_LIST", "📋")
EMOJI_ADD = _emoji("EMOJI_ADD", "➕")
EMOJI_REMOVE = _emoji("EMOJI_REMOVE", "➖")
EMOJI_WARN = _emoji("EMOJI_WARN", "⚠️")
EMOJI_USER = _emoji("EMOJI_USER", "👤")
EMOJI_LOG = _emoji("EMOJI_LOG", "📜")
EMOJI_HELP = _emoji("EMOJI_HELP", "❓")
