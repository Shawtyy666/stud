"""Импорт CSV из терминала после применения миграций."""

import argparse
import json

from app.config import CSV_PATH, database_url
from app.csv_import import CsvImportError, import_students_from_csv
from app.database import make_engine, make_session_factory
from app.repository import StudentRepository


def main():
    parser = argparse.ArgumentParser(description="Импорт результатов студентов из CSV")
    parser.add_argument("path", nargs="?", default=str(CSV_PATH), help="Путь к students.csv")
    args = parser.parse_args()
    engine = make_engine(database_url())
    try:
        with make_session_factory(engine)() as session:
            result = import_students_from_csv(StudentRepository(session), args.path)
            print(json.dumps(result, ensure_ascii=False))
    except CsvImportError as exc:
        parser.exit(1, f"Ошибка CSV: {exc}\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
