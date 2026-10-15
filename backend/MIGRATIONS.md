# Миграции базы данных

Alembic — единственный механизм изменения схемы БД.

## Локальная существующая база

После резервной копии один раз отметить текущую схему как исходную:

```powershell
cd backend
alembic stamp head
```

Команда не создаёт, не удаляет и не меняет таблицы; она добавляет только служебную запись Alembic о версии схемы.

## Новая база

```powershell
cd backend
alembic upgrade head
```

## Следующее изменение схемы

После изменения моделей создать и проверить миграцию:

```powershell
cd backend
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Перед production-deploy выполнить `alembic upgrade head`, а затем запустить приложение. Не запускайте `alembic downgrade` на production без резервной копии и проверки.
