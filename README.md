# Metrics API

Сервис принимает метрики (x, y, z) от устройств и считает по ним статистику: min, max, count, sum, median — по одному устройству или по всем устройствам пользователя за выбранный период.

Стек: Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL.

## Запуск в Docker

```bash
docker compose up --build
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- OpenAPI-схема: http://localhost:8000/openapi.json

Таблицы создаются автоматически при старте приложения. Данные PostgreSQL хранятся в volume `pgdata`; удалить их можно командой `docker compose down -v`.

## Локальный запуск (без Docker для API)

Нужен Python 3.10+ и запущенный PostgreSQL. Его можно поднять из compose:

```bash
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Строка подключения задаётся переменной окружения `DATABASE_URL`, по умолчанию:

```
postgresql+psycopg://postgres:postgres@localhost:5432/metrics
```

## API

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/users` | Создать пользователя |
| GET | `/api/users/{id}/analytics?from=&to=` | Статистика по всем устройствам пользователя и по каждому отдельно |
| POST | `/api/devices` | Создать устройство (можно привязать к пользователю) |
| POST | `/api/devices/{id}/metrics` | Записать метрику устройства |
| GET | `/api/devices/{id}/analytics?from=&to=` | Статистика по устройству |

`from` и `to` — необязательные границы периода (включительно) в формате ISO 8601, например `2026-10-10T12:00:00Z`. Время без часового пояса считается UTC. Время метрики проставляет сервер в момент записи.

Коды ответов: `201` — создано, `400` — ошибка валидации (пустое имя, несуществующий `userId`, `from` позже `to` и т. п.), `404` — пользователь или устройство не найдены.

### Пример

```bash
USER_ID=$(curl -s -X POST localhost:8000/api/users \
  -H 'Content-Type: application/json' -d '{"name": "Иван"}' | jq -r .id)

DEVICE_ID=$(curl -s -X POST localhost:8000/api/devices \
  -H 'Content-Type: application/json' -d "{\"userId\": \"$USER_ID\"}" | jq -r .id)

curl -s -X POST localhost:8000/api/devices/$DEVICE_ID/metrics \
  -H 'Content-Type: application/json' -d '{"x": 1.5, "y": 2, "z": -3}'

curl -s "localhost:8000/api/devices/$DEVICE_ID/analytics"
curl -s "localhost:8000/api/users/$USER_ID/analytics?from=2026-01-01T00:00:00Z"
```

Ответ статистики по устройству:

```json
{
  "deviceId": "…",
  "statistics": {
    "x": {"min": 1.5, "max": 1.5, "count": 1, "sum": 1.5, "median": 1.5},
    "y": {"min": 2.0, "max": 2.0, "count": 1, "sum": 2.0, "median": 2.0},
    "z": {"min": -3.0, "max": -3.0, "count": 1, "sum": -3.0, "median": -3.0}
  }
}
```

Если за период нет метрик, `count` = 0, `sum` = 0.0, а `min`, `max`, `median` = `null`.

Ответ статистики по пользователю:

```json
{
  "userId": "…",
  "aggregated": {"x": {…}, "y": {…}, "z": {…}},
  "devices": [
    {"deviceId": "…", "statistics": {"x": {…}, "y": {…}, "z": {…}}}
  ]
}
```

## Структура

```
app/
  main.py    — создание приложения, создание таблиц, обработчик ошибок валидации
  api.py     — эндпоинты и схемы запросов
  models.py  — модели SQLAlchemy (users, devices, metrics)
  stats.py   — расчёт статистики
  db.py      — подключение к БД и сессия
```
