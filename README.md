# Fitness Chicken

Telegram Mini App + бот: план упражнений на день, прогресс, календарь «Мой успех», админка каталога.

**Стек:** FastAPI + aiogram 3 + SQLite + статический Mini App (`frontend/`).

---

## 1. Подготовка `.env`

```powershell
copy .env.example .env
```

| Переменная | Что указать |
|------------|-------------|
| `BOT_TOKEN` | токен от [@BotFather](https://t.me/BotFather) |
| `WEBAPP_URL` | HTTPS URL миниаппа |
| `ADMIN_IDS` | твой Telegram user id |
| `TIMEZONE` | например `Europe/Moscow` |
| `REMINDER_TIMES` | например `09:00,16:00,21:00` |
| `DATABASE_URL` | локально или Netrun — см. ниже |
| `CHANNEL_ID` / `CHANNEL_INVITE_LINK` | закрытый канал с видео (опционально) |

Узнать свой id: [@userinfobot](https://t.me/userinfobot).

---

## 2. Локальный запуск (без Docker)

```powershell
cd C:\Users\Anna\Desktop\42\fitness_chicken
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

В `.env`:

```text
DATABASE_URL=sqlite+aiosqlite:///./fitness.db
```

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

БД: файл `fitness.db` в корне проекта.

Для миниаппа в Telegram нужен HTTPS-туннель на порт `8000` (cloudflared / ngrok), URL — в `WEBAPP_URL`, затем `/start` в боте.

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --protocol http2 --url http://localhost:8000
```

**Не** держи локальный бот и бота на Netrun с одним `BOT_TOKEN` одновременно.

---

## 3. Заливка на Netrun

`docker-compose.yml` **не нужен**. Достаточно `Dockerfile`.

Netrun даёт постоянную папку **`/data`**: всё, что туда записано, переживает публикацию нового кода. В кабинете — вкладка **«Данные»** (скачать / загрузить `fitness.db`).

### Dockerfile уже настроен так

```text
DATABASE_URL=sqlite+aiosqlite:////data/fitness.db
```

(четыре слэша = абсолютный путь `/data/fitness.db`)

### Шаги

1. Запушь код на GitHub (**без** `.env`).
2. На [Netrun](https://netrun.io) обнови проект из GitHub (только Dockerfile, без compose).
3. В настройках / секретах проекта:

```text
BOT_TOKEN=...
WEBAPP_URL=https://твой-проект.netrun.io
ADMIN_IDS=...
TIMEZONE=Europe/Moscow
REMINDER_TIMES=09:00,16:00,21:00
DATABASE_URL=sqlite+aiosqlite:////data/fitness.db
CHANNEL_ID=...
CHANNEL_INVITE_LINK=...
```

4. Опубликуй заново → вкладка **«Данные»**: должен появиться `fitness.db`. Если файл на месте и растёт после использования — база сохраняется.
5. В боте `/start`. Бэкап: **`/backup`** (админ).

### Про «чистку БД» при старте

В коде **нет** удаления базы. При старте (`app/db.py` → `init_db`):

1. `create_all` — только создаёт **недостающие** таблицы, данные не трогает.
2. `seed_catalog_if_empty` — заливает `catalog_seed.json` **только если каталог пустой**.

Если после деплоя снова «чистая» БД — файл писался **не в** `/data` (старый путь) или том ещё не был постоянным. С путём `////data/fitness.db` и вкладкой «Данные» это должно уйти.

Полная перезапись каталога бывает только если вручную нажать в админке «Загрузить из catalog_seed.json» (`/api/catalog/reload-seed`).

---

## Полезные команды бота

| Команда | Кто | Описание |
|---------|-----|----------|
| `/start` | все | приветствие + кнопка миниаппа |
| `/today` | все | прогресс базы за сегодня |
| `/add_ex` | админ | добавить упражнение |
| `/list_ex` | админ | список каталога |
| `/backup` | админ | скачать `fitness.db` |
| `/export_catalog` | админ | каталог в JSON |

Формат: `/add_ex category|Название|описание|https://t.me/...`  
Категории: `slot1`, `slot2`, `slot3`, `posture`, `neck`, `muscle_glutes_legs`, `muscle_arms`, `muscle_core_back`.

Тексты напоминаний: `data/pet_names.txt`, `data/reminder_phrases.txt`.

---

## Структура

```text
app/           # FastAPI, бот, модели, сервисы
frontend/      # Mini App
data/          # catalog_seed.json, тексты напоминаний
Dockerfile     # для Netrun (БД → /data/fitness.db)
.env.example
```
