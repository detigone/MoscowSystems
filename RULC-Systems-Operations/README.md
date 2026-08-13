# RU:LC Systems Operations

Discord-бот инфраструктуры сети **RU:LC Systems**: синхронизация ролей, autorole, условные роли, рассылка, `/config`, ER:LC stats (позже перенос в Roblox-бот).

## Возможности

### Синхронизация ролей
Роли синхронизируются между Discord-серверами группы — **отдельная команда `:team` в игре не нужна**, если игровые роли дублируются через Discord.

### Autorole и условные роли
- Autorole участнику и боту при входе
- Роль A при наличии роли B

### Рассылка
Сообщения из канала главного сервера → webhook-каналы фракций

### ER:LC
| Команда | Описание |
|---|---|
| `/erlc игроки` | Список игроков на сервере |
| `/erlc рейтинг активности` | Рейтинг активности |
| `/erlc рейтинг команд` | Топ команд |
| `/erlc рейтинг смертей` | Топ смертей |
| `/erlc рейтинг убийств` | Топ убийств |
| `/erlc статистика игроков` | График онлайна за 24ч |
| `/erlc статистика команд` | График команд |
| `/erlc статистика машин` | График спавна машин |

### Голосовой счётчик
Канал с названием `╭・📡 ・Игроков на сервере: 12` — обновляется автоматически.

### `/config` (только CONFIG_DISCORD_IDS)
Интерактивная панель с кнопками и меню: sync, autorole, conditional, broadcast, voice, ER:LC, оформление.

## Структура проекта

```
RULC-Systems-Operations/
├── main.py                 # Точка входа
├── bot/
│   ├── app.py              # RoleSyncBot, загрузка расширений
│   ├── settings.py         # Переменные окружения (.env)
│   ├── core/
│   │   └── checks.py       # Проверка доступа к /config
│   ├── db/
│   │   ├── schema.py       # SQL-схема SQLite
│   │   └── database.py     # Методы работы с БД
│   ├── cogs/
│   │   ├── config.py       # /config — панель настроек
│   │   ├── erlc.py         # /erlc — игроки, рейтинги, графики
│   │   ├── tasks.py        # Фоновые задачи (статистика, ГС)
│   │   └── events/         # Слушатели Discord-событий
│   │       ├── guild.py    # on_ready, on_guild_join
│   │       ├── sync.py     # role sync, autorole, conditional
│   │       └── broadcast.py
│   ├── services/           # Бизнес-логика
│   └── ui/
│       └── config_panel.py # Интерактивная панель /config
└── data/                   # SQLite (создаётся автоматически)
```

## Быстрый старт

```powershell
copy .env.example .env
py -3 -m pip install -r requirements.txt
py -3 main.py
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `DISCORD_TOKEN` | Токен бота |
| `CONFIG_DISCORD_IDS` | Discord ID людей с доступом к `/config` |
| `DEV_GUILD_IDS` | Быстрая синхронизация slash-команд |
| `BLOXLINK_API_KEY` | Опционально, Bloxlink guild API |
| `DATABASE_PATH` | Локальный файл SQLite (по умолчанию `data/bot.db` в папке проекта) |

## Локальная база данных

Бот хранит все настройки и статистику в **одном файле SQLite** на твоём компьютере или VPS — без облака и без отдельного сервера БД.

- Файл по умолчанию: `RULC-Systems-Operations/data/bot.db`
- Создаётся **автоматически** при первом запуске бота
- Папка `data/` в репозитории есть, сам `.db` в git не попадает (см. `.gitignore`)
- Путь можно переопределить в `.env` через `DATABASE_PATH`

При старте в логах будет строка вида: `Local database: F:\...\role-sync-bot\data\bot.db`

## Intents и права

- **Server Members Intent**, **Message Content Intent**
- `Manage Roles`, `Manage Channels` (для переименования ГС)

## Совместимость

| Система | Роль |
|---|---|
| **Bloxlink** | Верификация Roblox (опционально) |
| **CADLY** | CAD/смены — параллельно |
| **MoscowSystems Bot** | Роли, рассылка, ER:LC статистика |

MIT License
