# RU:LC Systems

Три Discord-бота — три папки, один VPS.

| Папка | Бот | Назначение |
|-------|-----|------------|
| [`CycleRM/`](CycleRM/) | **CycleRM** | Staff: `/punish`, смены, ER:LC (форк ERM) |
| [`RULC-Systems-Roblox/`](RULC-Systems-Roblox/) | **RU:LC Systems Roblox** | Баллы, `/поиск`, ER:LC stats |
| [`RULC-Systems-Operations/`](RULC-Systems-Operations/) | **RU:LC Systems Operations** | Sync ролей, рассылка, `/config` |

## Связь CycleRM → Roblox

```
/punish  →  CycleRM  →  POST http://127.0.0.1:8081/internal/punishment  →  баллы
revoke   →  POST /internal/punishment/revoke
```

Секрет один и тот же:
- CycleRM: `RULC_ROBLOX_SECRET`
- Roblox: `INTERNAL_API_SECRET`

## Запуск (по порядку)

```powershell
# 1. Roblox (internal API)
cd F:\MoscowSystems\RULC-Systems-Roblox
python main.py

# 2. CycleRM
cd F:\MoscowSystems\CycleRM
python main.py

# 3. Operations
cd F:\MoscowSystems\RULC-Systems-Operations
python main.py
```

Подробнее: README в каждой папке.
