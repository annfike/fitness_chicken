# Fitness Chicken

Telegram Mini App + бот: план упражнений на день, прогресс, календарь «Мой успех», админка каталога.

**Стек:** FastAPI + aiogram 3 + SQLite + статический Mini App (`frontend/`).

---

## 1. Подготовка `.env`

```powershell
copy .env.example .env
```

Заполни в `.env`:

| Переменная | Что указать |
|------------|-------------|
| `BOT_TOKEN` | токен от [@BotFather](https://t.me/BotFather) |
| `WEBAPP_URL` | HTTPS URL миниаппа (см. ниже) |
| `ADMIN_IDS` | твой Telegram user id |
| `TIMEZONE` | например `Europe/Moscow` |
| `REMINDER_TIMES` | например `09:00,16:00,21:00` |
| `DATABASE_URL` | для Docker / Netrun — см. ниже |

Узнать свой id: [@userinfobot](https://t.me/userinfobot).

---

## 2. Локальный запуск в Docker

Нужны [Docker Desktop](https://www.docker.com/products/docker-desktop/) (не на паузе) и файл `.env` в корне проекта.

На Windows **не** запускай `sudo dockerd` — движок даёт Docker Desktop (иконка кита → Resume, если на паузе).

### Запуск контейнера

```powershell
cd C:\Users\Anna\Desktop\42\fitness_chicken

docker compose up --build
```

Первый раз образ соберётся дольше. Приложение слушает **http://127.0.0.1:8080/**

В логах должно быть примерно:

- `SQLite file: /app/data/fitness.db`
- `Uvicorn running on http://0.0.0.0:8080`
- `Starting bot polling` / имя бота

Остановка:

```powershell
docker compose down
```

### HTTPS для миниаппа (cloudflared)

Telegram не открывает `localhost`. Нужен туннель на порт **8080**.

Если команда `cloudflared` «не распознана», используй полный путь:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --protocol http2 --url http://localhost:8080
```

В выводе появится URL вида `https://….trycloudflare.com`.

1. Впиши его в `.env`:
   ```text
   WEBAPP_URL=https://….trycloudflare.com
   ```
2. Пересоздай контейнер, чтобы подтянуть `.env`:
   ```powershell
   docker compose up -d --force-recreate
   ```
3. В боте отправь **`/start`**.

Окно с `cloudflared` оставляй открытым, пока тестируешь миниапп. После перезапуска туннеля URL обычно **меняется** — снова обнови `WEBAPP_URL`, recreate, `/start`.

### Проверка

1. Браузер: [http://127.0.0.1:8080/](http://127.0.0.1:8080/) — страница миниаппа.
2. БД на томе:

```powershell
docker compose exec app ls -la /app/data
```

Должен быть `fitness.db`.

### Если меняла код — какие команды

Код в контейнер попадает только при **сборке образа**. После правок в `app/`, `frontend/`, `Dockerfile`, `requirements.txt`:

```powershell
docker compose up --build -d
```

| Что меняла | Команда |
|------------|---------|
| Python / frontend / Dockerfile / requirements | `docker compose up --build -d` |
| Только `.env` (токен, WEBAPP_URL, …) | `docker compose up -d --force-recreate` |
| Остановить | `docker compose down` |
| Остановить и **удалить БД** в томе | `docker compose down -v` |

Логи:

```powershell
docker compose logs -f --tail 100
```

После смены `WEBAPP_URL` — снова **`/start`** в Telegram.

### База данных в Docker

В `docker-compose.yml` том `dbdata` → `/app/data`. В контейнере:

```text
DATABASE_URL=sqlite+aiosqlite:////app/data/fitness.db
```

(четыре слэша = абсолютный путь). Том сохраняется между `--build`, пока не сделаешь `down -v`.

### Важно

Не запускай локальный Docker-бот и бота на Netrun **с одним `BOT_TOKEN` одновременно** — конфликт polling.

---

## 3. Заливка на Netrun

### Что уже есть в репозитории

- `Dockerfile` — приложение на порту **8080**
- `docker-compose.yml` — том `dbdata` → `/app/data` (постоянное хранилище)
- сид каталога кладётся в образ как `/app/seed/catalog_seed.json` (том не перекрывает сид)

### Шаги

1. Запушь код на GitHub (без `.env` — он в `.gitignore`).
2. На [Netrun](https://netrun.io) создай/обнови проект из GitHub.
3. Запуск через **Docker / docker-compose** (не «голый» Python без тома — иначе БД снова будет пропадать при деплое).
4. В секретах / переменных окружения Netrun укажи:

```text
BOT_TOKEN=...
WEBAPP_URL=https://твой-проект.netrun.io
ADMIN_IDS=...
TIMEZONE=Europe/Moscow
REMINDER_TIMES=09:00,16:00,21:00
DATABASE_URL=sqlite+aiosqlite:////app/data/fitness.db
```

`WEBAPP_URL` — ссылка проекта из кабинета Netrun (HTTPS).  
`DATABASE_URL` — **тот же** абсолютный путь, что в Docker (четыре слэша).

5. После деплоя: `/start` в боте → миниапп.  
   Если каталог пустой — подтянется из сида; дальше правь в админке / `/add_ex`.
6. Бэкап БД: команда бота **`/backup`** (только админ) — пришлёт файл в Telegram.

### Чем Netrun отличается от локального Docker

| | Локально | Netrun |
|--|----------|--------|
| URL миниаппа | туннель или только проверка `http://127.0.0.1:8080` | `https://….netrun.io` в `WEBAPP_URL` |
| Порт наружу | `ports: "8080:8080"` в compose | Netrun сам проксирует `expose: 8080` |
| БД | том Docker `dbdata` | том из `docker-compose.yml` (должен переживать обновление кода) |
| Секреты | файл `.env` | панель Netrun (не коммитить в git) |
| Тариф | — | free = тест; для 24/7 бота нужен платный режим |

После смены `WEBAPP_URL` снова отправь боту `/start` (обновится кнопка меню).

---

## 4. Запуск без Docker (опционально)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

В `.env` для локалки без контейнера:

```text
DATABASE_URL=sqlite+aiosqlite:///./fitness.db
```

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Файл БД появится в корне проекта: `fitness.db`.

---

## Полезные команды бота

| Команда | Кто | Описание |
|---------|-----|----------|
| `/start` | все | приветствие + кнопка миниаппа |
| `/today` | все | прогресс базы за сегодня |
| `/add_ex` | админ | добавить упражнение в каталог |
| `/list_ex` | админ | список каталога |
| `/backup` | админ | скачать `fitness.db` |
| `/export_catalog` | админ | выгрузить каталог в JSON |

Формат: `/add_ex category|Название|описание|https://t.me/...`  
Категории: `slot1`, `slot2`, `slot3`, `posture`, `neck`, `muscle_glutes_legs`, `muscle_arms`, `muscle_core_back`.

---

## Структура

```text
app/           # FastAPI, бот, модели, сервисы
frontend/      # Mini App
data/          # catalog_seed.json (в репо)
Dockerfile
docker-compose.yml
.env.example
```
