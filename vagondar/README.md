# VagonDar

Учёт подачи/уборки вагонов и расчёт стоимости по тарифу. Django 5.2.

## Локальный запуск

```bash
# из корня репозитория
py -m venv .venv
.venv\Scripts\activate
pip install -r vagondar/requirements.txt
cd vagondar
python manage.py migrate
python manage.py runserver
```

Локально без переменных окружения включается DEBUG и используется `db.sqlite3`.

Тесты: `python manage.py test`

Формула расчёта описана в `main/calculations.py` — это единственное место, где она живёт
(страница и Excel-экспорт используют её же).

## Render

**Web Service** (Root Directory: `vagondar`):

| Параметр        | Значение                     |
|-----------------|------------------------------|
| Build Command   | `./build.sh`                 |
| Start Command   | `gunicorn vagondar.wsgi`     |

**Environment variables:**

| Переменная     | Значение                                                       |
|----------------|----------------------------------------------------------------|
| `SECRET_KEY`   | случайная строка (обязательно, без неё сайт не запустится)     |
| `DATABASE_URL` | Internal Database URL от PostgreSQL                            |

Сгенерировать ключ:
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

## Перенос данных SQLite → PostgreSQL

Сначала добавить в `requirements.txt` строку `psycopg[binary]==3.3.8`.

`-X utf8` обязателен на Windows, иначе кириллица в файле сломается.

```bash
# 1. Выгрузить данные из SQLite (файл db.sqlite3 с прода положить в vagondar/)
python manage.py migrate
python -X utf8 manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e admin.logentry -e sessions --indent 2 -o data.json

# 2. Загрузить в PostgreSQL (External Database URL)
set DATABASE_URL=postgresql://...
python manage.py migrate
python -X utf8 manage.py loaddata data.json
```

## Резервная копия

Профиль → «Скачать резервную копию данных (JSON)» (только для staff).
Восстановление: `python manage.py loaddata <файл>.json`.
