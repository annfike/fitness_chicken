FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite+aiosqlite:////data/fitness.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
# Seed/texts live outside /app/data so the persistent volume does not hide them
COPY data/catalog_seed.json ./seed/catalog_seed.json
COPY data/pet_names.txt ./seed/pet_names.txt
COPY data/reminder_phrases.txt ./seed/reminder_phrases.txt

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
