# Server Deploy (Pull + Cron)

## 1. Clone/pull on server
```bash
cd /opt
git clone https://github.com/attilabirtha/a2t.ro.git
cd a2t.ro
# later updates:
# git pull
```

## 2. Prepare config
```bash
cp .env.server.example .env.server
mkdir -p /opt/a2t.ro/secrets
# put Google Ads service-account key JSON at:
# /opt/a2t.ro/secrets/google-ads-key.json
```

Edit `.env.server` with real values.

## 3. Permissions
```bash
chmod +x scripts/refresh_a2t.sh scripts/install_cron.sh
mkdir -p /var/www/dev.proclick.ro/a2t.ro/data/output
```

## 4. First refresh run
```bash
PROJECT_DIR=/opt/a2t.ro WEB_ROOT=/var/www/dev.proclick.ro/a2t.ro ./scripts/refresh_a2t.sh
```

## 5. Install hourly cron
```bash
PROJECT_DIR=/opt/a2t.ro ./scripts/install_cron.sh
```

## 6. Nginx location
Serve `/var/www/dev.proclick.ro/a2t.ro` at `https://dev.proclick.ro/a2t.ro/`.

## 7. Update flow
```bash
cd /opt/a2t.ro
git pull
PROJECT_DIR=/opt/a2t.ro WEB_ROOT=/var/www/dev.proclick.ro/a2t.ro ./scripts/refresh_a2t.sh
```
