# Frontend Humary

В проекте используется один подход к frontend: серверный рендеринг **Jinja2 + vanilla JavaScript + CSS**.

## Где находится код

- `html/` — Jinja2-шаблоны страниц;
- `js/` — JavaScript-модули браузера;
- `css/` — исходные стили компонентов;
- `css/app.css` — собранный CSS-бандл, который подключают шаблоны;
- `scripts/build_css.py` — сборка и проверка CSS-бандла;
- `images/`, `fonts/`, `vendor/` — статические ресурсы.

## Правила разработки

- Новые страницы и разметку добавлять в `html/`, маршруты — в `backend/app/routers/pages.py`.
- Интерактивность добавлять отдельными модулями в `js/` и подключать из нужного шаблона.
- Стили добавлять в `css/components/`, затем пересобирать бандл:

  ```powershell
  .\.venv\Scripts\python.exe frontend\scripts\build_css.py
  .\.venv\Scripts\python.exe frontend\scripts\build_css.py --check
  ```

- Не добавлять React, Vite, npm-сборку или второй каталог frontend: FastAPI отдаёт этот frontend напрямую через `/css`, `/js`, `/images`, `/fonts` и `/vendor`.

Так у проекта одна точка входа, нет двух версий интерфейса и нет лишних зависимостей Node.js на сервере.
