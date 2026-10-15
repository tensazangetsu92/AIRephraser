# Запуск Humary через Docker Compose

1. На сервере скопируйте `deploy/production.env.example` в `deploy/production.env` и заполните все значения. Пароль в `DATABASE_URL` должен совпадать с `POSTGRES_PASSWORD`; хост БД оставьте `db`.
2. До запуска настройте HTTPS reverse proxy (Nginx или Caddy) для домена. Он должен направлять запросы на `http://127.0.0.1:8000`.
3. В корне проекта выполните:

   ```bash
   docker compose up -d --build
   ```

   Контейнер `migrate` сначала применит Alembic-миграции и завершится. После успешного завершения запустится `app`.
4. Проверьте состояние и логи:

   ```bash
   docker compose ps
   docker compose logs -f app migrate
   curl http://127.0.0.1:8000/health
   ```

PostgreSQL не имеет опубликованного порта и доступна только контейнерам Compose. Данные сохраняются в Docker volume `postgres_data`; для резервного копирования используйте инструкции из `deploy/backup/README.md`.

Для обновления кода:

```bash
docker compose up -d --build
```

Не используйте `docker compose down -v`: эта команда удаляет volume с PostgreSQL и все данные.
