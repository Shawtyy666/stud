import csv
from collections import Counter
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.database import make_engine, make_session_factory
from app.main import create_app
from app.repository import StudentRepository
from app.schemas import StudentCreate

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "students.csv"


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url, config


@pytest.fixture
def client(database):
    with TestClient(create_app(database[0])) as client:
        yield client


@pytest.fixture
def student():
    return {"last_name": "Ли", "first_name": "Иван", "faculty": "АВТФ", "course": "Физика", "score": 29}


def test_crud(client, student):
    created = client.post("/students", json=student)
    assert created.status_code == 201
    record = created.json()
    record_id = record.pop("id")
    assert record == student
    assert client.get(f"/students/{record_id}").json()["score"] == 29
    assert len(client.get("/students").json()) == 1
    updated = client.put(f"/students/{record_id}", json={**student, "score": 90})
    assert updated.status_code == 200
    assert updated.json()["score"] == 90
    assert client.delete(f"/students/{record_id}").status_code == 204
    assert client.get(f"/students/{record_id}").status_code == 404
    assert client.get("/students").json() == []


def test_repository_persistence(database, student):
    engine = make_engine(database[0])
    sessions = make_session_factory(engine)
    try:
        with sessions() as session:
            record_id = StudentRepository(session).create(StudentCreate(**student)).id
        with sessions() as session:
            repository = StudentRepository(session)
            assert repository.get(record_id).first_name == "Иван"
            assert repository.update(record_id, StudentCreate(**{**student, "score": 100})).score == 100
        with sessions() as session:
            repository = StudentRepository(session)
            assert repository.get(record_id).score == 100
            assert repository.delete(record_id)
        with sessions() as session:
            assert StudentRepository(session).get(record_id) is None
    finally:
        engine.dispose()


def test_filters(client, student):
    for changes in ({}, {"score": 30}, {"score": 0}, {"course": "История", "score": 100}, {"faculty": "ФПМИ", "score": 10}):
        assert client.post("/students", json={**student, **changes}).status_code == 201
    assert len(client.get("/students", params={"faculty": "АВТФ"}).json()) == 4
    assert client.get("/students", params={"faculty": "' OR 1=1 --"}).json() == []
    assert client.get("/courses").json() == ["История", "Физика"]
    low = client.get("/students/below-30", params={"course": "Физика"}).json()
    assert sorted(row["score"] for row in low) == [0, 10, 29]
    average = client.get("/faculties/average-score", params={"faculty": "АВТФ"})
    assert average.status_code == 200
    assert average.json() == {"faculty": "АВТФ", "average_score": 39.75, "records_count": 4}


def test_import_and_real_data_queries(client):
    assert client.post("/students/import").json() == {"imported": 215, "already_imported": False}
    assert client.post("/students/import").json() == {"imported": 0, "already_imported": True}
    actual = client.get("/students", params={"limit": 1000}).json()
    assert len(actual) == 215
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as file:
        source = list(csv.DictReader(file))
    assert Counter((r["last_name"], r["first_name"], r["faculty"], r["course"], r["score"]) for r in actual) == Counter(
        (r["Фамилия"], r["Имя"], r["Факультет"], r["Курс"], int(r["Оценка"])) for r in source
    )
    assert client.get("/courses").json() == sorted({r["Курс"] for r in source})
    for faculty in {r["Факультет"] for r in source}:
        scores = [int(r["Оценка"]) for r in source if r["Факультет"] == faculty]
        result = client.get("/faculties/average-score", params={"faculty": faculty}).json()
        assert result["average_score"] == pytest.approx(sum(scores) / len(scores))
        assert result["records_count"] == len(scores)
        assert len(client.get("/students", params={"faculty": faculty, "limit": 1000}).json()) == len(scores)
    for course in {r["Курс"] for r in source}:
        rows = client.get("/students/below-30", params={"course": course, "limit": 1000}).json()
        assert len(rows) == sum(r["Курс"] == course and int(r["Оценка"]) < 30 for r in source)


def test_pagination(client):
    client.post("/students/import")
    first = client.get("/students", params={"limit": 2}).json()
    second = client.get("/students", params={"limit": 2, "offset": 2}).json()
    assert len(first) == len(second) == 2
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})


def test_bad_import_is_atomic(database, tmp_path):
    file = tmp_path / "bad.csv"
    file.write_text("Фамилия,Имя,Факультет,Курс,Оценка\nЛи,Иван,АВТФ,Физика,20\nКим,Петр,ФПМИ,Физика,101\n", encoding="utf-8")
    with TestClient(create_app(database[0], file)) as client:
        assert client.post("/students/import").status_code == 400
        assert client.get("/students").json() == []
        file.write_text("Фамилия,Имя,Факультет,Курс,Оценка\nЛи,Иван,АВТФ,Физика,20\n", encoding="utf-8")
        assert client.post("/students/import").json()["imported"] == 1


def test_migration_upgrade_downgrade(database):
    url, config = database
    engine = make_engine(url)
    try:
        assert {"students", "csv_imports"} <= set(inspect(engine).get_table_names())
        command.downgrade(config, "base")
        assert "students" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "students" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


@pytest.mark.parametrize("method,path", [("get", "/students/999"), ("delete", "/students/999"), ("put", "/students/999")])
def test_not_found(client, student, method, path):
    kwargs = {"json": student} if method == "put" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 404


@pytest.mark.parametrize("score", [-1, 101, "20", True, 29.5])
def test_invalid_score(client, student, score):
    assert client.post("/students", json={**student, "score": score}).status_code == 422


def test_empty_and_validation(client):
    assert client.get("/courses").json() == []
    assert client.get("/students/below-30", params={"course": "Нет"}).json() == []
    assert client.get("/faculties/average-score", params={"faculty": "Нет"}).status_code == 404
    for path in ("/students?limit=0", "/students?offset=-1", "/students?limit=1001", "/students/below-30", "/students/0"):
        assert client.get(path).status_code == 422
    assert client.get("/docs").status_code == 200
