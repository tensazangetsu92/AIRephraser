# Тестовый домен и HTTPS через Caddy

## 1. Создайте тестовый поддомен

Например, выберите `staging.example.ru`. В панели DNS домена добавьте запись:

```text
Тип: A
Имя: staging
Значение: публичный IPv4-адрес сервера
TTL: 300
```

Если у сервера есть публичный IPv6, добавьте соответствующую AAAA-запись.
Дождитесь, пока домен начнёт указывать на сервер. До этого Caddy не сможет
подтвердить владение доменом и получить сертификат.

## 2. Откройте порты сервера

В firewall сервера и панели хостинга должны быть открыты входящие TCP-порты
`80` и `443`. Для HTTP/3 также нужен UDP-порт `443`.

Не открывайте PostgreSQL (`5432`) и FastAPI (`8000`) наружу.

## 3. Заполните переменные окружения

Создайте два файла, которых нет в Git:

```bash
cp deploy/production.env.example deploy/production.env
cp deploy/caddy.env.example deploy/caddy.env
```

В обоих файлах укажите один и тот же поддомен:

```env
# deploy/caddy.env
SITE_DOMAIN=staging.example.ru
ACME_EMAIL=admin@example.ru

# deploy/production.env
FRONTEND_URL=https://staging.example.ru
CORS_ORIGINS=https://staging.example.ru
YANDEX_REDIRECT_URI=https://staging.example.ru/auth/yandex/callback
VK_ID_REDIRECT_URI=https://staging.example.ru/auth/vk/callback
```

`COOKIE_SECURE=true` оставьте включённым. Это позволит браузеру отправлять
cookie авторизации только по HTTPS.

## 4. Запустите сайт

```bash
docker compose up -d --build
docker compose logs -f caddy app
```

Caddy самостоятельно запросит сертификат Let's Encrypt, сохранит его в volume
`caddy_data` и затем будет автоматически продлевать. После успешного запуска
откройте `https://staging.example.ru/health`.

## 5. Перед запуском основного домена

Проверьте на тестовом поддомене регистрацию, email-коды, cookie, вход после
перезагрузки, обработку текста, Word-файлы и историю. Затем замените домен в
обоих env-файлах на основной, обновите DNS-запись и выполните:

```bash
docker compose up -d --build
```

Не удаляйте volumes `postgres_data` и `caddy_data`: в первом находится база,
во втором — сертификаты Caddy.
