# Деплой (коли будете готові до VPS)

Локальна підготовка вже можлива без домену. Цей файл — чеклист на момент хостингу.

## 1. Сервер

- Ubuntu 22.04+, Docker + Docker Compose
- Мінімум 4 GB RAM (AI worker), краще 8 GB для 2–3 воркерів

## 2. Секрети

Див. [SECURITY.md](./SECURITY.md). Коротко:

```bash
cp .env.example .env
# заповнити SECRET_KEY, JWT_SECRET, паролі, токени
APP_ENV=production
DEBUG=false
```

## 3. Запуск

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec api alembic upgrade head
```

## 4. Бекап (cron)

```cron
0 3 * * * cd /opt/ai-wall-visualizer && ./scripts/backup-db.sh >> /var/log/wallviz-backup.log 2>&1
```

## 5. Оновлення

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec api alembic upgrade head
```

## 6. Моніторинг

Ops-бот: `OPS_TELEGRAM_BOT_TOKEN`, `OPS_TELEGRAM_CHAT_ID` → `docker compose up -d ops`

## GitHub

1. Створіть **private** repo на GitHub.
2. Локально (якщо ще немає remote):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin git@github.com:YOU/ai-wall-visualizer.git
   git push -u origin main
   ```
3. Переконайтесь: `git status` не показує `.env` (має бути в `.gitignore`).
