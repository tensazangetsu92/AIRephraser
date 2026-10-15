# Отдельная тестовая PostgreSQL и миграции

Тестовая БД должна быть отдельной от production. Для этого Compose запускается
с именем проекта `humary-staging`. Docker автоматически создаст отдельный
volume `humary-staging_postgres_data`; production позже будет использовать,
например, `humary-postgres_data`.

## Подготовка файлов на сервере

```bash
cp deploy/production.env.example deploy/staging.env
cp deploy/caddy.env.example deploy/staging-caddy.env
cp deploy/compose.staging.env.example deploy/compose.staging.env
```

В `deploy/staging.env` задайте отдельные пароль PostgreSQL, `SECRET_KEY` и
`SESSION_SECRET_KEY`. Укажите тестовый URL во всех полях:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg2://humary:STAGING_DATABASE_PASSWORD@db:5432/humary_staging
POSTGRES_DB=humary_staging
POSTGRES_USER=humary
POSTGRES_PASSWORD=STAGING_DATABASE_PASSWORD
FRONTEND_URL=https://staging.example.ru
CORS_ORIGINS=https://staging.example.ru
COOKIE_SECURE=true
DEV_LOG_VERIFICATION_CODE=false
```

В `deploy/staging-caddy.env` укажите тот же поддомен:

```env
SITE_DOMAIN=staging.example.ru
ACME_EMAIL=admin@example.ru
```

Перед запуском добавьте DNS-запись `staging.example.ru` на IP сервера и
откройте TCP-порты 80 и 443.

## Создание тестовой БД и запуск миграций

Выполните из корня проекта:

```bash
docker compose --env-file deploy/compose.staging.env -p humary-staging up --build migrate
```

Команда:

1. создаст отдельный контейнер PostgreSQL и volume;
2. дождётся `healthy`-состояния PostgreSQL;
3. выполнит внутри контейнера `migrate` команду `alembic -c alembic.ini upgrade head`;
4. завершится с кодом 0 только при успешном применении всех миграций.

Проверьте журнал миграции:

```bash
docker compose --env-file deploy/compose.staging.env -p humary-staging logs migrate
```

Затем запустите тестовый сайт:

```bash
docker compose --env-file deploy/compose.staging.env -p humary-staging up -d app caddy
docker compose --env-file deploy/compose.staging.env -p humary-staging ps
```

Откройте `https://staging.example.ru/health`. Ответ должен быть:

```json
{"status":"ok","checks":{"database":"ok"}}
```

`deploy/staging.env` и `deploy/staging-caddy.env` исключены из Git и Docker
build context. Не используйте для staging команду `docker compose down -v`:
она удалит тестовую базу. Для обычной остановки используйте:

```bash
docker compose --env-file deploy/compose.staging.env -p humary-staging down
```
