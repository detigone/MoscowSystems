# RU:LC Systems Roblox

Игровой бот сети: **баллы**, **`/поиск`**, ER:LC stats (позже).

CycleRM шлёт наказания сюда — баллы начисляются **только в этом боте**.

## Internal API (для CycleRM)

| Endpoint | Описание |
|----------|----------|
| `GET /health` | Проверка |
| `POST /internal/punishment` | Новое наказание + баллы |
| `POST /internal/punishment/revoke` | Revoke + откат баллов |

Заголовок: `Authorization: Bearer <INTERNAL_API_SECRET>`

## Запуск

```powershell
cd RULC-Systems-Roblox
py -3 -m pip install -r requirements.txt
copy .env.example .env
python main.py
```

В CycleRM `.env`:
```
RULC_ROBLOX_URL=http://127.0.0.1:8081
RULC_ROBLOX_SECRET=<тот же секрет>
```

## Баллы по умолчанию

| Тип | Баллы |
|-----|-------|
| Warning | 1 |
| Kick | 3 |
| Ban | 10 |
| BOLO | 5 |
