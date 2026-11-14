from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Student(Base):
    """Одна строка CSV: результат студента по одному предмету."""

    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_students_score"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str] = mapped_column(String(200), nullable=False)
    faculty: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    course: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)


class CsvImport(Base):
    """История загруженных файлов для защиты от повторного импорта."""

    __tablename__ = "csv_imports"

    checksum: Mapped[str] = mapped_column(String(64), primary_key=True)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False)


class User(Base):
    """Зарегистрированный пользователь; пароль хранится только в виде хеша."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(250), nullable=False)


class UserSession(Base):
    """Храним хеш токена, чтобы выход немедленно отзывал доступ."""

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
