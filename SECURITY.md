# Безпека та секрети

## Що ніколи не потрапляє в Git

- `.env` — паролі, токени ботів, `SECRET_KEY`, `JWT_SECRET`
- `backups/` — дампи БД
- `storage/projects/`, `storage/textures/` — фото клієнтів
- `certbot/`, `*.pem` — SSL-ключі

У репозиторії лише `.env.example` з **порожніми** плейсхолдерами.

## Перед продакшеном

1. Скопіюйте `.env.example` → `.env`
2. Локально (Windows) — один раз:
   ```powershell
   .\scripts\apply-security.ps1
   ```
   Оновить секрети, паролі адмінів у БД, зробить тестовий бекап і задачу щодня о 03:00.
   Нові паролі — у `credentials.local.txt` (не в git).
3. Або вручну: `.\scripts\generate-secrets.ps1` + змініть `.env`
4. Встановіть `APP_ENV=production` на VPS — API **не стартує** зі слабкими секретами.
4. Змініть паролі демо-адмінів або створіть нових через platform-admin.
5. Якщо токен Telegram колись потрапив у git або `.env.example` — **відкличте його в @BotFather** і видайте новий.

## Паролі магазинів

- Кожен `StoreAdmin` має свій `password_hash` (bcrypt) — не в `.env`.
- Токен бота магазину зберігається в `stores.telegram_bot_token` — не комітиться.

## Ізоляція магазинів (multi-tenant)

| Дані | Ізоляція |
|------|----------|
| Кольори фарби (ціна, наявність) | `store_colors` по `store_id` |
| Знижки | `store_discounts` по `store_id` |
| Ціни фасовок фарби | `store_brand_pack_prices` по `store_id` |
| Декор (матеріали, відтінки, фасовки) | `decorative_materials.store_id` |
| Ліди, проєкти | `store_id` на записі |

Спільні глобально: **назви брендів** і **об'єми фасовок** (`brands`, `brand_pack_sizes`). Якщо два магазини потребують різних лінійок упаковки — створюйте окремі бренди з унікальними назвами.

Перевірка:
```bash
docker compose exec api python /scripts/verify-store-isolation.py
```

## Бекап БД

```powershell
.\scripts\backup-db.ps1
```

На Linux/VPS — `scripts/backup-db.sh` у cron (наприклад щодня о 03:00).

## GitHub

- Репозиторій — **приватний** рекомендовано.
- Пушити: код, міграції, `docker-compose`, `.env.example`.
- Не пушити: `.env`, бекапи, `storage/`, сертифікати.

Якщо секрет вже був у історії git — ротація токенів + `git filter-repo` або новий репозиторій.
