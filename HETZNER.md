# Покроковий деплой на Hetzner (для новачків)

Робіть **по одному кроці**. Після кожного — напишіть у чат «крок N готово» + що вийшло (IP, домен тощо).

---

## Крок 1. Реєстрація Hetzner

1. Відкрийте **https://www.hetzner.com/cloud**
2. **Sign up** → email, пароль, підтвердження
3. Додайте **картку** (списання ~€0.01 для перевірки, потім повертають)

---

## Крок 2. SSH-ключ на Windows (без пароля на сервері)

У PowerShell:

```powershell
ssh-keygen -t ed25519 -C "wallviz-hetzner" -f "$env:USERPROFILE\.ssh\id_ed25519_hetzner"
```

На питання passphrase — Enter (порожньо) або свій пароль.

Показати публічний ключ (скопіюйте **весь** рядок):

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_hetzner.pub"
```

---

## Крок 3. Створити сервер у Hetzner

1. **Console** → **New project** → назва `wallviz`
2. **Add Server**:
   - **Location:** Falkenstein (fsn1) або Helsinki
   - **Image:** Ubuntu **22.04**
   - **Type:** **CPX31** (4 vCPU, 8 GB RAM) — мінімум для AI
   - **Networking:** Public IPv4 ✓
   - **SSH keys:** **Add SSH key** → вставте ключ з кроку 2
   - **Name:** `wallviz-prod`
3. **Create & Buy**
4. Запишіть **IPv4** (наприклад `95.217.12.34`)

---

## Крок 4. Перше підключення SSH

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_hetzner" root@ВАШ_IP
```

Якщо питає `Are you sure...` → `yes`.

Ви в консолі сервера, якщо бачите `root@wallviz-prod:~#`.

---

## Крок 5. Підготовка сервера (Docker, firewall)

На сервері (після `git clone` — крок 6) або одразу:

```bash
curl -fsSL https://raw.githubusercontent.com/ВАШ_ЛОГІН/ai-wall-visualizer/main/scripts/hetzner-setup-server.sh | bash
```

**Поки немає GitHub** — скопіюйте вручну з проєкту `scripts/hetzner-setup-server.sh` на сервер або виконайте команди з файлу.

---

## Крок 6. Код на сервер

### Варіант A — GitHub (краще)

На ПК: push у private repo.

На сервері:

```bash
cd /opt
git clone git@github.com:ВАШ_ЛОГІН/ai-wall-visualizer.git
cd ai-wall-visualizer
```

### Варіант B — без GitHub

На ПК (PowerShell):

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ed25519_hetzner" -r "C:\Users\Nazar Lakusta\Projects\ai-wall-visualizer" root@ВАШ_IP:/opt/
```

На сервері: `cd /opt/ai-wall-visualizer`

---

## Крок 7. Домен і DNS

1. Купіть домен (Namecheap, Cloudflare, тощо)
2. **DNS → A record:**
   - Name: `@` (або `paint` для піддомену)
   - Value: **IP сервера**
   - TTL: 300
3. Зачекайте 5–30 хв. Перевірка з ПК:

```powershell
nslookup ваш-домен.com
```

IP має збігатися з Hetzner.

---

## Крок 8. Файл `.env` на сервері

```bash
cd /opt/ai-wall-visualizer
cp .env.production.example .env
nano .env
```

Обов’язково змініть:

```env
APP_ENV=production
DEBUG=false
SECRET_KEY=...          # 48+ випадкових символів
JWT_SECRET=...
ADMIN_PASSWORD=...
PLATFORM_ADMIN_PASSWORD=...
TELEGRAM_BOT_TOKEN=...
WEBAPP_URL=https://ваш-домен.com/app
```

Зберегти: `Ctrl+O`, Enter, `Ctrl+X`.

---

## Крок 9. SSL (HTTPS) + запуск

```bash
export DOMAIN=ваш-домен.com
export EMAIL=ваш@email.com
chmod +x scripts/*.sh
./scripts/init-letsencrypt.sh
```

Скрипт: HTTP nginx → certbot → prod nginx + docker.

Перевірка: `https://ваш-домен.com/health` → `{"status":"ok"}` або подібне.

---

## Крок 10. Міграції і адмін

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python /scripts/rotate-admin-passwords.py
```

Відкрийте:
- `https://ваш-домен.com/admin/`
- `https://ваш-домен.com/platform/`

---

## Крок 11. Telegram

1. @BotFather → ваш бот → **Menu Button** / Web App
2. URL: `https://ваш-домен.com/app`
3. На сервері:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate bot
```

---

## Крок 12. Бекап (cron)

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/ai-wall-visualizer && ./scripts/backup-db.sh >> /var/log/wallviz-backup.log 2>&1") | crontab -
```

---

## Корисні команди

```bash
# Статус
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Логи API
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api --tail 50

# Оновлення після git pull
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

---

## Що написати в чат після кроку 3

«Крок 3 готово, IP: `x.x.x.x`» — підемо далі з SSH і доменом.
