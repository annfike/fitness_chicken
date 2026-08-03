# Fitness Chicken — Telegram Mini App + бот

Учёт прогресса по **общему плану упражнений на день**. Бот три раза в день смотрит БД и лично напоминает тем, кто ещё не закрыл день.

## Стек

- **Python** — FastAPI (API + раздача Mini App) + **aiogram 3** (бот)
- **SQLite** (по умолчанию) через SQLAlchemy async
- **APScheduler** — напоминания в `09:00`, `15:00`, `21:00` (настраивается)
- **Frontend** — статичный Mini App (`frontend/`)

## Быстрый старт

1. Создай бота в [@BotFather](https://t.me/BotFather), получи токен.
2. В BotFather: **Bot Settings → Menu Button** (или `/setmenubutton`) — укажи URL Mini App (нужен HTTPS; для локалки — [ngrok](https://ngrok.com) / Cloudflare Tunnel).
3. Скопируй конфиг:

```bash
copy .env.example .env
```

Заполни `BOT_TOKEN`, `WEBAPP_URL`, `ADMIN_IDS` (свой Telegram id).

4. Установи зависимости и запусти:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. В Telegram: `/start` у бота → «Открыть тренировку».
## План дня (авто)

План **не задаётся каждый день вручную**. Из каталога собирается персональный день:

1. Слот 1 и 2 — одни и те же упражнения каждый день  
2. Слот 3 — пользователь выбирает вариант  
3. 3 упражнения на осанку — из ещё не сделанных на неделе (круг заново, если всё пройдено)  
4. Шея — выбор варианта  
5. Бонус — ещё 3 осанки  
6. Силовая каждый день: попа/ноги · руки · кор/спина — с балансом за неделю  

Админ наполняет каталог:

```text
/add_ex posture|Лодочка|описание|https://t.me/channel/12
/list_ex posture
```

Категории: `slot1`, `slot2`, `slot3`, `posture`, `neck`, `muscle_glutes_legs`, `muscle_arms`, `muscle_core_back`.

Стартовый seed: `data/catalog_seed.json` (подставляется, если каталог пуст).


## Как работают напоминания

В `REMINDER_TIMES` (например `09:00,15:00,21:00`) по таймзоне `TIMEZONE` планировщик:

1. Берёт план на **сегодня**
2. Для каждого пользователя считает прогресс в БД
3. Если база не закрыта — шлёт **личное** сообщение со списком остатка и кнопкой в Mini App

## API (кратко)

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `/api/me` | Текущий пользователь |
| GET | `/api/plan/today` | План + галочки на сегодня |
| GET | `/api/plan/{date}` | План на дату |
| POST | `/api/progress` | `{ "exercise_id", "completed" }` |
| POST | `/api/plan` | Создать/заменить план (админ) |

Все запросы (кроме статики) требуют заголовок `X-Telegram-Init-Data`.

## Структура

```text
app/
  main.py      # FastAPI + lifespan (бот + scheduler)
  bot.py       # команды и напоминания
  api.py       # REST для Mini App
  models.py    # User, DailyPlan, Exercise, Progress
  services.py  # бизнес-логика
  auth.py      # проверка initData
frontend/      # Mini App
```

## Дальше (по желанию)

- PostgreSQL вместо SQLite
- Админка в Mini App для плана
- История по дням / стрик
- Проверка подписки на канал перед доступом
