from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CsvImport, Student
from app.schemas import StudentCreate


class StudentRepository:
    """SQLAlchemy-класс для INSERT, SELECT, UPDATE, DELETE и отчётов."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, data: StudentCreate) -> Student:
        student = Student(**data.model_dump())
        self.session.add(student)
        self.session.commit()
        return student

    def get(self, student_id: int) -> Student | None:
        return self.session.get(Student, student_id)

    def list(self, faculty: str | None = None, offset: int = 0, limit: int = 100) -> list[Student]:
        query = select(Student)
        if faculty is not None:
            query = query.where(Student.faculty == faculty)
        return list(self.session.scalars(query.order_by(Student.id).offset(offset).limit(limit)))

    def update(self, student_id: int, data: StudentCreate) -> Student | None:
        student = self.get(student_id)
        if student is None:
            return None
        for field, value in data.model_dump().items():
            setattr(student, field, value)
        self.session.commit()
        return student

    def delete(self, student_id: int) -> bool:
        student = self.get(student_id)
        if student is None:
            return False
        self.session.delete(student)
        self.session.commit()
        return True

    def courses(self) -> list[str]:
        return list(self.session.scalars(select(Student.course).distinct().order_by(Student.course)))

    def below_30(self, course: str, offset: int = 0, limit: int = 100) -> list[Student]:
        query = select(Student).where(Student.course == course, Student.score < 30)
        return list(self.session.scalars(query.order_by(Student.id).offset(offset).limit(limit)))

    def faculty_average(self, faculty: str) -> dict | None:
        average, count = self.session.execute(
            select(func.avg(Student.score), func.count(Student.id)).where(Student.faculty == faculty)
        ).one()
        if count == 0:
            return None
        return {"faculty": faculty, "average_score": float(average), "records_count": count}

    def import_students(self, students: list[StudentCreate], checksum: str) -> dict:
        try:
            with self.session.begin():
                if self.session.get(CsvImport, checksum) is not None:
                    return {"imported": 0, "already_imported": True}
                self.session.add(CsvImport(checksum=checksum, records_count=len(students)))
                self.session.flush()
                self.session.add_all(Student(**student.model_dump()) for student in students)
            return {"imported": len(students), "already_imported": False}
        except IntegrityError:
            # Если другой запрос успел импортировать тот же файл, повтор пропускается.
            self.session.rollback()
            if self.session.get(CsvImport, checksum) is not None:
                return {"imported": 0, "already_imported": True}
            raise
