import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import CSV_PATH, database_url
from app.csv_import import HEADERS, CsvImportError, import_students_from_csv
from app.database import make_engine, make_session_factory
from app.repository import StudentRepository
from app.schemas import FacultyAverage, ImportResult, StudentCreate, StudentRead

StudentId = Annotated[int, ApiPath(ge=1)]
Filter = Annotated[str, Query(min_length=1, max_length=200)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=1000)]


def create_app(url: str | None = None, csv_path: Path | None = None) -> FastAPI:
    engine = make_engine(url or database_url())
    sessions = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(application):
        yield
        engine.dispose()

    application = FastAPI(title="Студенты: CRUD", version="1.0.0", lifespan=lifespan)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]})

    def get_repository():
        with sessions() as session:
            yield StudentRepository(session)

    Repository = Annotated[StudentRepository, Depends(get_repository)]

    @application.get("/")
    def index():
        return {"message": "Студенты: CRUD", "docs": "/docs"}

    @application.post("/students/import", response_model=ImportResult, tags=["CSV"])
    def import_csv(repository: Repository):
        try:
            return import_students_from_csv(repository, csv_path or CSV_PATH)
        except CsvImportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/students/export", tags=["CSV"])
    def export_csv(repository: Repository):
        """Скачать все записи в формате исходного students.csv."""
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(HEADERS)
        for student in repository.export_rows():
            writer.writerow([
                student.last_name,
                student.first_name,
                student.faculty,
                student.course,
                student.score,
            ])
        return Response(
            content=output.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="students.csv"'},
        )

    @application.get("/students/below-30", response_model=list[StudentRead], tags=["Выборки"])
    def below_30(course: Filter, repository: Repository, offset: Offset = 0, limit: Limit = 100):
        return repository.below_30(course, offset, limit)

    @application.get("/students", response_model=list[StudentRead], tags=["CRUD"])
    def students(repository: Repository, faculty: Annotated[str | None, Query(min_length=1, max_length=200)] = None, offset: Offset = 0, limit: Limit = 100):
        return repository.list(faculty, offset, limit)

    @application.post("/students", response_model=StudentRead, status_code=201, tags=["CRUD"])
    def create_student(data: StudentCreate, repository: Repository):
        return repository.create(data)

    @application.get("/students/{student_id}", response_model=StudentRead, tags=["CRUD"])
    def get_student(student_id: StudentId, repository: Repository):
        student = repository.get(student_id)
        if student is None:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        return student

    @application.put("/students/{student_id}", response_model=StudentRead, tags=["CRUD"])
    def update_student(student_id: StudentId, data: StudentCreate, repository: Repository):
        student = repository.update(student_id, data)
        if student is None:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        return student

    @application.delete("/students/{student_id}", status_code=204, tags=["CRUD"])
    def delete_student(student_id: StudentId, repository: Repository):
        if not repository.delete(student_id):
            raise HTTPException(status_code=404, detail="Запись не найдена")
        return Response(status_code=204)

    @application.get("/courses", response_model=list[str], tags=["Выборки"])
    def courses(repository: Repository):
        return repository.courses()

    @application.get("/faculties/average-score", response_model=FacultyAverage, tags=["Выборки"])
    def average(faculty: Filter, repository: Repository):
        result = repository.faculty_average(faculty)
        if result is None:
            raise HTTPException(status_code=404, detail="Факультет не найден")
        return result

    return application


app = create_app()
