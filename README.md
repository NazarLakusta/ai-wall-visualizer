# AI Wall Visualizer

Telegram Bot + Mini App для підбору фарби та декоративних покриттів на фотографіях інтер'єру.

## Стек

- **Backend:** FastAPI, SQLAlchemy, Alembic, Celery, Redis
- **AI:** SegFormer (Hugging Face), OpenCV, Pillow
- **DB:** PostgreSQL
- **Frontend:** Vanilla JS + HTML5 Canvas (Mini App + Admin)
- **Bot:** aiogram 3 (long polling, multi-store)
- **Infra:** Docker Compose, Nginx

## Швидкий старт

```bash
cp .env.example .env
# Вкажіть TELEGRAM_BOT_TOKEN у .env

docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python /scripts/seed_test_project.py
```

Сервіси:
- API: http://localhost/api/health
- Mini App: http://localhost/app/
- Admin: http://localhost/admin/ (admin@example.com / admin123)

**Безпека, бекапи, ізоляція магазинів:** [SECURITY.md](./SECURITY.md) · **Деплой на VPS:** [DEPLOY.md](./DEPLOY.md)

## Архітектура

```
Telegram Bot → FastAPI → Redis/Celery → AI Worker (SegFormer) → PostgreSQL
                    ↓
              Mini App (Canvas render)
```

## Конфігурація

| Змінна | Опис |
|--------|------|
| `RETENTION_HOURS` | Термін зберігання проєктів (24–48) |
| `MAX_UPLOAD_MB` | Макс. розмір фото (20) |
| `WEBAPP_URL` | URL Mini App для Telegram (HTTPS у prod) |
| `SEGFORMER_MODEL_ID` | Модель сегментації стін (за замовч. nvidia/segformer-b5-finetuned-ade-640-640) |
| `OPS_TELEGRAM_BOT_TOKEN` | Токен **вашого** ops-бота (@BotFather) |
| `OPS_TELEGRAM_CHAT_ID` | Ваш chat ID для сповіщень (бот покаже після `/start`) |
| `OPS_HEARTBEAT_INTERVAL_MINUTES` | Звіт про сервер (за замовч. 15 хв) |

## Ops monitor (Telegram)

Окремий бот для вас як власника платформи — не для магазинів.

1. Створіть бота в @BotFather → скопіюйте токен у `OPS_TELEGRAM_BOT_TOKEN`
2. `docker compose up -d ops`
3. Напишіть боту `/start` — він покаже ваш `OPS_TELEGRAM_CHAT_ID`
4. Додайте chat ID в `.env` і перезапустіть: `docker compose up -d --force-recreate ops`

**Команди:** `/status` — стан зараз.

**Автоматично:** кожні N хвилин — звіт (БД, Redis, черга AI, магазини, заявки).  
**Миттєво:** помилка AI, висока черга, падіння БД/Redis.

## AI: SegFormer

Worker завантажує модель SegFormer при першому завданні. Перший запуск може зайняти кілька хвилин (завантаження ваг з Hugging Face).

Без успішного завантаження моделі обробка фото завершиться помилкою — переконайтесь, що контейнер `worker` має доступ до мережі та достатньо RAM.

Для локального тесту редактора без AI використовуйте кнопку **«Тестове фото»** у боті.

## Multi-store

Кожен магазин — окремий tenant: свої ціни (`store_colors`), знижки (`store_discounts`), ціни фасовок (`store_brand_pack_prices`), декор (`decorative_materials`). Після міграції `015` масові зміни цін у вкладці «Ціни» не чіпають інші магазини.

Перевірка ізоляції:
```bash
docker compose exec api python /scripts/verify-store-isolation.py
```

Кожен магазин може мати власного Telegram-бота. Після зміни токена в адмінці:

```bash
docker compose up -d --force-recreate bot
```

## Команди бота

| Команда | Дія |
|---------|-----|
| `/start` | Головне меню |
| `/help` | Довідка для клієнта |
