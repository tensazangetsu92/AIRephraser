# Production alongside staging

Production and staging run as different Docker Compose projects on the same
server. They have separate PostgreSQL containers, volumes, environment files
and application containers. Production Caddy is the only process that binds
public ports 80 and 443; it routes each domain to the correct private app.

## Before the first launch

1. Confirm that both `humary.ru` and `staging.humary.ru` A records point to
   the VPS.
2. In the Yandex OAuth and VK ID dashboards, add these production callbacks:

   ```text
   https://humary.ru/auth/yandex/callback
   https://humary.ru/auth/vk/callback
   ```

3. On the server, copy and fill the three production files. Use a new
   PostgreSQL password, `SECRET_KEY` and `SESSION_SECRET_KEY`; do not reuse
   the staging values. SMTP and GigaChat credentials may be reused.

   ```bash
   cd /opt/humary && cp deploy/production.env.example deploy/production.env && cp deploy/production-caddy.env.example deploy/production-caddy.env && cp deploy/compose.production.env.example deploy/compose.production.env
   ```

## Launch sequence

Run the commands in this order. None of them deletes the staging database.

```bash
cd /opt/humary && docker network create humary-proxy 2>/dev/null || true
```

```bash
cd /opt/humary && docker compose --env-file deploy/compose.staging.env -p humary-staging up -d --build app caddy
```

```bash
cd /opt/humary && docker compose --env-file deploy/compose.production.env -p humary-production up -d --build migrate app
```

The previous command creates `humary-production_postgres_data`, applies
migrations to that new database, and starts the production app. It does not
yet change incoming HTTPS traffic.

Switch the public proxy with a brief interruption (normally a few seconds):

```bash
cd /opt/humary && docker compose --env-file deploy/compose.staging.env -p humary-staging stop caddy && docker compose --env-file deploy/compose.production.env -p humary-production up -d caddy
```

## Verify

```bash
cd /opt/humary && docker compose --env-file deploy/compose.staging.env -p humary-staging ps && docker compose --env-file deploy/compose.production.env -p humary-production ps && curl -fsS https://staging.humary.ru/health && echo && curl -fsS https://humary.ru/health
```

Both health checks must return `{"status":"ok","checks":{"database":"ok"}}`.

Never run `docker compose down -v` for either project: it removes that
project's PostgreSQL volume and all of its data.
