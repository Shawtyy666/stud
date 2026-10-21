"""Чтение и проверка CSV до начала транзакции записи."""

import csv
import hashlib
import io
import re
from pathlib import Path

from pydantic import ValidationError

from app.schemas import StudentCreate

HEADERS = ("Фамилия", "Имя", "Факультет", "Курс", "Оценка")


class CsvImportError(ValueError):
    pass


def read_students_csv(path: str | Path) -> tuple[list[StudentCreate], str]:
    try:
        content = Path(path).read_bytes()
        text = content.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise CsvImportError("Не удалось прочитать CSV в кодировке UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    students = []
    try:
        if reader.fieldnames != list(HEADERS):
            raise CsvImportError("Ожидаемые столбцы: " + ", ".join(HEADERS))
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise CsvImportError(f"Строка {reader.line_num}: неверное число столбцов")
            raw_score = row["Оценка"].strip()
            if not re.fullmatch(r"[0-9]{1,3}", raw_score):
                raise CsvImportError(f"Строка {reader.line_num}: оценка должна быть целым числом от 0 до 100")
            try:
                students.append(StudentCreate(
                    last_name=row["Фамилия"], first_name=row["Имя"],
                    faculty=row["Факультет"], course=row["Курс"], score=int(raw_score),
                ))
            except ValidationError as exc:
                raise CsvImportError(f"Строка {reader.line_num}: пустое/слишком длинное поле или оценка вне диапазона 0–100") from exc
    except csv.Error as exc:
        raise CsvImportError(f"Повреждённый CSV около строки {reader.line_num}") from exc
    return students, hashlib.sha256(content).hexdigest()


def import_students_from_csv(repository, path: str | Path) -> dict:
    students, checksum = read_students_csv(path)
    return repository.import_students(students, checksum)
