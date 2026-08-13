# CycleRM

**CycleRM** — форк [CycleRM](https://github.com/mikeywhiston/CycleRM) для сети **RU:LC Systems**.

Staff-модерация: `/punish`, смены, ER:LC и остальной функционал CycleRM.

> **Баллы игроков** начисляются в **RU:LC Systems Roblox**, не здесь.  
> После каждого `/punish` CycleRM отправляет событие в Roblox-бот.

## Быстрый старт

```powershell
cd CycleRM
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.template .env
# заполнить .env
python main.py
```

## Обязательно в `.env`

| Переменная | Описание |
|---|---|
| `ENVIRONMENT` | `CUSTOM` для self-host |
| `CUSTOM_BOT_TOKEN` | Токен Discord-бота CycleRM |
| `MONGO_URL` | MongoDB |
| `BLOXLINK_API_KEY` | Bloxlink |
| `PRC_API_KEY` | ER:LC / PRC API |
| `RULC_ROBLOX_URL` | URL internal API Roblox-бота, напр. `http://127.0.0.1:8081` |
| `RULC_ROBLOX_SECRET` | Общий секрет (тот же в Roblox-боте) |

## Связь с RU:LC Systems Roblox

```
/punish  →  CycleRM MongoDB  →  POST /internal/punishment  →  Roblox SQLite + баллы
revoke   →  POST /internal/punishment/revoke
```

Игроки смотрят профиль: **`/поиск`** в RU:LC Systems Roblox.

## Лицензия

CC BY-NC-SA 4.0 — см. [LICENSE](LICENSE) и [ATTRIBUTION.md](ATTRIBUTION.md).

## Брендинг и emoji

См. [BRANDING.md](BRANDING.md) — как заменить emoji и аватар бота.
