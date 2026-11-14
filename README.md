# Студенты: CRUD и авторизация на FastAPI, SQLAlchemy и Alembic

Учебное API с регистрацией, входом, выходом и защищёнными CRUD-операциями для работы с результатами студентов из `students.csv`. Используются Python 3.10+, FastAPI, Pydantic 2, SQLAlchemy 2 и Alembic. База данных — SQLite, отдельный сервер БД не нужен.

## Модель данных

Одна запись таблицы `students` соответствует одной строке CSV: студент, факультет, предмет и оценка. Поле «Курс» в исходном файле содержит названия предметов, а не номер года обучения.

| Столбец CSV | Поле модели | Тип |
|---|---|---|
| — | id | Целочисленный первичный ключ |
| Фамилия | last_name | Строка до 200 символов |
| Имя | first_name | Строка до 200 символов |
| Факультет | faculty | Строка до 200 символов, индекс |
| Курс | course | Строка до 200 символов, индекс |
| Оценка | score | Целое число от 0 до 100 |

Пустые текстовые значения запрещены; пробелы по краям удаляются. В CSV 215 строк, включая одно полное повторение. Импорт сохраняет все строки. По имени и фамилии нельзя надёжно различить тёзок, поэтому записи не объединяются в предполагаемые личности. Средний балл считается по всем записям факультета, включая разные предметы.

В таблице `csv_imports` сохраняется SHA-256 файла и число импортированных строк. Это предотвращает повторную загрузку одного и того же файла.

## Установка

Распакуйте архив и откройте терминал в папке с этим README. Создайте виртуальное окружение:

```bash
python -m venv .venv
```

Windows PowerShell (активация окружения не требуется):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe import_students.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m alembic upgrade head
.venv/bin/python import_students.py
.venv/bin/python -m uvicorn app.main:app --reload
```

Ожидаемый результат первого импорта: `{"imported": 215, "already_imported": false}`. Файл `students.db` создаётся в папке проекта. Данные сохраняются после перезапуска сервера. Таблицы создаёт Alembic: перед первым запуском обязательно выполните `upgrade head`.

Откройте http://127.0.0.1:8000/docs и воспользуйтесь **Try it out**. Остановка сервера — Ctrl+C. Вместо импорта через терминал можно вызвать `POST /students/import` с Bearer-токеном: он загрузит включённый в проект `data/students.csv`.

## Авторизация (user_token)

Для всех маршрутов работы с данными необходим токен зарегистрированного пользователя. Открытыми остаются `/auth/register`, `/auth/login`, `/auth/logout` (для выхода нужен токен), а также Swagger UI `/docs` и схема `/openapi.json`.

1. `POST /auth/register` — регистрация по `username` и `password` (минимум 8 символов пароля).
2. `POST /auth/login` — вход с теми же данными. В ответе возвращается `user_token`.
3. Передавайте токен в заголовке `Authorization: Bearer <user_token>`. В Swagger UI (`/docs`) нажмите **Authorize** и вставьте полученный токен (без слова `Bearer`).
4. `POST /auth/logout` с тем же заголовком — выход: сессия удаляется и повторное использование токена возвращает HTTP 401.

Пример:

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d '{"username":"student1","password":"example-password-123"}'
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d '{"username":"student1","password":"example-password-123"}'
curl http://127.0.0.1:8000/students -H "Authorization: Bearer ВАШ_ТОКЕН"
curl -X POST http://127.0.0.1:8000/auth/logout -H "Authorization: Bearer ВАШ_ТОКЕН"
```

Пароли не хранятся открытым текстом: используется PBKDF2-SHA256 с уникальной солью. Токены генерируются случайным образом; база хранит только SHA-256 токена. Срок действия — 24 часа, выход отзывает токен досрочно. Отсутствие/неверный/истёкший токен возвращает HTTP 401. Роль только для чтения и refresh-токены в этой версии не реализованы.

После обновления существующей базы выполните `python -m alembic upgrade head`: миграция `0002` добавляет таблицы `users` и `user_sessions`. Существующие записи студентов сохраняются.

## Эндпоинты

| Метод | Путь | Действие |
|---|---|---|
| POST | `/auth/register` | Создать пользователя |
| POST | `/auth/login` | Получить токен доступа |
| POST | `/auth/logout` | Отозвать текущий токен |
| POST | `/students` | INSERT: создание записи, ответ 201 |
| GET | `/students` | SELECT: список записей |
| GET | `/students/{student_id}` | SELECT: запись по ID |
| PUT | `/students/{student_id}` | UPDATE: замена всех полей записи |
| DELETE | `/students/{student_id}` | DELETE: удаление, ответ 204 без тела |
| POST | `/students/import` | Импорт поставляемого CSV |
| GET | `/students/export` | Скачать все записи из базы в CSV исходного формата |
| GET | `/students?faculty=АВТФ` | Студенты выбранного факультета |
| GET | `/courses` | Отсортированный список уникальных курсов |
| GET | `/students/below-30?course=Мат.%20Анализ` | Результаты по курсу строго ниже 30 |
| GET | `/faculties/average-score?faculty=АВТФ` | Средний балл по факультету |

Списки записей поддерживают `offset` (от 0) и `limit` (от 1 до 1000, по умолчанию 100). Для получения всех 215 исходных строк используйте `/students?limit=1000`. При увеличении данных получайте страницы с разными `offset`. Фильтры работают по точному названию с учётом регистра.

Оценка 30 не попадает в выборку «ниже 30»; оценка 0 попадает. Список возвращает записи результатов, поэтому студент с несколькими предметами может встречаться несколько раз. Пустая выборка возвращает `[]`.

Средний балл рассчитывается SQL-функцией `AVG`, без предварительного округления:

```json
{
  "faculty": "Название факультета",
  "average_score": 39.75,
  "records_count": 4
}
```

Это пример формата, а не значение из исходного CSV. Для факультета без записей возвращается 404: средний балл для пустого набора не определён.

## Выгрузка CSV (дополнительное задание)

Эндпоинт `GET /students/export` возвращает **все записи** из базы, включая созданные или изменённые после импорта, без ограничения стандартной пагинацией. Скачиваемый файл называется `students.csv` и содержит столбцы `Фамилия,Имя,Факультет,Курс,Оценка` в исходном порядке. CSV кодируется в UTF-8 с BOM для удобного открытия в Excel. При пустой базе выгружается файл только с заголовками.

Пример загрузки файла с помощью curl:

```bash
curl -o students-export.csv http://127.0.0.1:8000/students/export
```

## Примеры запросов

Тело `POST /students` и `PUT /students/{student_id}`:

```json
{
  "last_name": "Иванов",
  "first_name": "Иван",
  "faculty": "АВТФ",
  "course": "Физика",
  "score": 75
}
```

При создании ID присваивается базой данных и возвращается вместе с остальными полями. `PUT` требует все пять полей. Пропущенное поле, лишнее поле, дробная оценка, числовая строка, пустая строка или оценка вне диапазона дают 422. Для отсутствующей записи чтение, изменение и удаление возвращают 404.

Примеры PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/students/import'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/students?limit=1000'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/courses'
```

Пример curl (macOS / Linux / Git Bash):

```bash
curl -G 'http://127.0.0.1:8000/students/below-30' --data-urlencode 'course=Мат. Анализ' --data-urlencode 'limit=1000'
curl -G 'http://127.0.0.1:8000/faculties/average-score' --data-urlencode 'faculty=АВТФ'
```

Полный набор запросов для VS Code REST Client находится в `examples/requests.http`. Для кириллических параметров также удобно использовать Swagger UI в `/docs`.

## Работа с базой и импорт

`StudentRepository` получает отдельную SQLAlchemy-сессию через FastAPI `Depends`. Методы `create`, `get`, `list`, `update`, `delete` реализуют CRUD. Метод `courses` использует `DISTINCT`, `below_30` — фильтр по предмету и оценке, `faculty_average` — `AVG` и `COUNT`. Значения передаются SQLAlchemy как параметры запроса.

Функция `import_students_from_csv(repository, path)` читает файл с русскими заголовками в UTF-8 (включая BOM). Сначала проверяются все строки, затем данные и отметка об импорте записываются одной транзакцией. При ошибке CSV частичного импорта нет. HTTP-метод при такой ошибке возвращает 400 с пояснением.

Повторный импорт идентичного файла возвращает `{"imported": 0, "already_imported": true}`. Он не восстанавливает удалённые записи и не отменяет ручные изменения. Изменённый файл имеет другую контрольную сумму и добавляется как новая партия; это добавление, а не синхронизация. Полное повторение строки внутри одного файла сохраняется.

Импорт другого файла через терминал:

```bash
python import_students.py path/to/students.csv
```

Здесь и далее `python` означает Python активированного окружения; без активации используйте путь к `.venv` из инструкций установки.

## Alembic

Начальная миграция `0001` создаёт таблицы, ограничение оценки и индексы. Автоматическое `create_all()` при старте не используется.

```bash
python -m alembic upgrade head
python -m alembic current
```

После изменения ORM-моделей новую миграцию можно подготовить командой:

```bash
python -m alembic revision --autogenerate -m "Update student model"
```

Проверьте полученный файл перед применением. Команда `python -m alembic downgrade base` удаляет таблицы и все их данные; для обычного запуска она не нужна.

Для другой базы SQLite задайте переменную `DATABASE_URL` одинаково для Alembic, импорта и приложения. Например, в PowerShell:

```powershell
$env:DATABASE_URL = 'sqlite:///./another.db'
```

В macOS / Linux: `export DATABASE_URL='sqlite:///./another.db'`. Выполняйте команды из папки проекта. По умолчанию приложение и миграции используют `students.db` в этой папке.

## Проверка

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Тесты API создают отдельную временную SQLite-базу и применяют реальную миграцию Alembic. Проверяются CRUD, сохранение данных между сессиями, фильтры, граница 30 баллов, средние значения, импорт 215 строк, отсутствие повторного импорта, ошибки CSV и откат миграции. Исходная рабочая база не используется.

В среде подготовки проекта выполнены **23 теста** из `tests/test_csv.py`: чтение реального файла, ошибки CSV и проверки схемы данных. Полный набор тестов API и миграций здесь не запускался, поскольку SQLAlchemy и Alembic отсутствовали, а установка зависимостей была недоступна. После установки зависимостей запустите полную команду выше. GitHub Actions также настроен на запуск полного набора тестов при push и pull request.

## Структура проекта

```text
app/
  config.py        — пути и настройки базы
  models.py        — ORM-модели SQLAlchemy
  schemas.py       — схемы запросов и ответов
  database.py      — движок и фабрика сессий
  repository.py    — CRUD и SQL-выборки
  csv_import.py    — чтение, проверка и импорт CSV
  main.py          — FastAPI и подключение репозитория
alembic/           — окружение и начальная миграция
data/students.csv  — исходные 215 строк
tests/             — проверки CSV, API и миграций
examples/          — примеры HTTP-запросов
import_students.py — запуск импорта из терминала
```

## Публикация на GitHub

Создайте пустой публичный репозиторий `students-crud`, затем выполните в папке проекта:

```bash
git init
git add .
git commit -m "Add students CRUD API and CSV import"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/students-crud.git
git push -u origin main
```

Замените `YOUR_USERNAME` своим именем. Загружайте исходники вместе с `data/students.csv` и миграциями. Виртуальное окружение, кэш и файл базы исключены через `.gitignore`.

Для сдачи приложите ссылку на репозиторий и прямую ссылку на `app/main.py`; операции с базой находятся в `app/repository.py`. Проверьте публичный доступ в приватном окне браузера и результат **Actions → Tests**.

Документация: [сессии SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [миграции Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
