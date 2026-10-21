from pathlib import Path

import pytest
from pydantic import ValidationError

from app.csv_import import CsvImportError, read_students_csv
from app.schemas import StudentCreate

ROOT = Path(__file__).resolve().parent.parent
HEADER = "Фамилия,Имя,Факультет,Курс,Оценка\n"


def test_actual_csv():
    students, checksum = read_students_csv(ROOT / "data" / "students.csv")
    assert len(students) == 215
    assert len(checksum) == 64
    assert students[0].model_dump() == {
        "last_name": "Ли", "first_name": "Иван", "faculty": "АВТФ",
        "course": "Теор. Механика", "score": 52,
    }
    assert len({tuple(student.model_dump().values()) for student in students}) == 214


@pytest.mark.parametrize("row", [
    "Ли,Иван,АВТФ,Физика,-1\n",
    "Ли,Иван,АВТФ,Физика,101\n",
    "Ли,Иван,АВТФ,Физика,29.5\n",
    "Ли,Иван,АВТФ,Физика,abc\n",
    "Ли,Иван,АВТФ,Физика\n",
    "Ли,Иван,АВТФ,Физика,20,лишнее\n",
    ",Иван,АВТФ,Физика,20\n",
    '"Ли,Иван,АВТФ,Физика,20\n',
])
def test_bad_csv(tmp_path, row):
    path = tmp_path / "bad.csv"
    path.write_text(HEADER + row, encoding="utf-8")
    with pytest.raises(CsvImportError):
        read_students_csv(path)


def test_bom(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text(HEADER + "Ли,Иван,АВТФ,Физика,0\n", encoding="utf-8-sig")
    assert read_students_csv(path)[0][0].score == 0


def test_bad_headers(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("wrong,header\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match="столбцы"):
        read_students_csv(path)


def test_missing_file(tmp_path):
    with pytest.raises(CsvImportError):
        read_students_csv(tmp_path / "missing.csv")


@pytest.mark.parametrize("score", [-1, 101, 29.5, True, "20", None])
def test_score_validation(score):
    with pytest.raises(ValidationError):
        StudentCreate(last_name="Ли", first_name="Иван", faculty="АВТФ", course="Физика", score=score)


@pytest.mark.parametrize("score", [0, 29, 30, 100])
def test_score_boundaries(score):
    assert StudentCreate(last_name="Ли", first_name="Иван", faculty="АВТФ", course="Физика", score=score).score == score


def test_whitespace():
    student = StudentCreate(last_name=" Ли ", first_name="Иван", faculty="АВТФ", course="Физика", score=20)
    assert student.last_name == "Ли"
