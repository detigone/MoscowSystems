# Брендинг CycleRM

## Текст

Пользовательские строки в коде используют **CycleRM** / **RU:LC Systems** вместо ERM.

Исключения (намеренно не менялись):
- `erm.py` — точка входа (имя файла из форка)
- `ERMProcessing` — имя базы MongoDB из ERM
- `ATTRIBUTION.md`, `LICENSE` — указание авторства оригинала
- Ссылки на `ermbot.xyz` в коде веб-панели (для self-host не используются)

## Цвета

| Константа | HEX | Назначение |
|-----------|-----|------------|
| `BRAND_COLOR` | `#4FC3F7` | Основной голубой акцент |
| `BRAND_COLOR_DARK` | `#0288D1` | Ошибки и security alerts |
| `BLANK_COLOR` | `#2B2D31` | Нейтральный embed |
| `GREEN_COLOR` | Discord green | Успех, join, on-duty |

Файл: `utils/constants.py`.

## Изображения и emoji

**В репозитории нет картинок.** ERM использует **кастомные emoji Discord** — они загружены на сервер ERM и в коде выглядят так:

```
<:ERMCheck:1111089850720976906>
```

На твоём сервере этих emoji **нет**, поэтому CycleRM по умолчанию использует unicode: ✅ ❌ ⏳ и т.д. (`utils/branding.py`).

### Свои emoji (опционально)

1. Подготовь PNG/GIF (рекомендуется 128×128, до 256 KB).
2. Discord → **Настройки сервера** → **Emoji** → **Загрузить emoji**.
3. Скопируй строку вида `<:CycleRMCheck:1234567890>`.
4. Добавь в `CycleRM/.env`:

```env
EMOJI_SUCCESS=<:CycleRMCheck:1234567890>
EMOJI_ERROR=<:CycleRMClose:1234567890>
EMOJI_PENDING=<:CycleRMPending:1234567890>
EMOJI_ALERT=<:CycleRMAlert:1234567890>
EMOJI_LIST=<:CycleRMList:1234567890>
EMOJI_ADD=<:CycleRMAdd:1234567890>
EMOJI_REMOVE=<:CycleRMRemove:1234567890>
EMOJI_WARN=<:CycleRMWarn:1234567890>
EMOJI_USER=<:CycleRMUser:1234567890>
EMOJI_LOG=<:CycleRMLog:1234567890>
EMOJI_HELP=<:CycleRMHelp:1234567890>
```

5. Перезапусти бота.

### Emoji приложения бота (Application Emojis)

Загружаются из `assets/emojis/*.png` при старте (`utils/emojis.py`):

| Имя файла | Использование |
|-----------|---------------|
| `check.png` | Включено / галочка |
| `xmark.png` | Выключено / крестик |
| `success.png` | Успешные действия |
| `error.png` | Ошибки |
| `WarningIcon.png` | Предупреждения PRC API |
| `loa.png` | Activity Notices (LOA/RA) |
| `log.png` | Punishments модуль |
| `shift.png` | Shift Management |
| `Clock.png` | Таймер / ожидание |
| `ShiftStarted.png` | On-duty |
| `ShiftBreak.png` | On-break |
| `ShiftEnded.png` | Off-duty |
| `arrow.png` | Навигация |
| `l_arrow.png` | Навигация (влево) |
| `security.png` | Anti-ping / security |

### Аватар бота

Меняется не в коде, а в [Discord Developer Portal](https://discord.com/developers/applications) → твоё приложение CycleRM → **Bot** → **Icon**.

### Thumbnail в embed (Staff Conduct)

После rebrand hardcoded CDN emoji ERM убраны; при желании поставь URL своей картинки в `embed.set_thumbnail(url="...")`.
