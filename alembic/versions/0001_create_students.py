"""Создание таблиц результатов студентов и истории импорта."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_name", sa.String(200), nullable=False),
        sa.Column("first_name", sa.String(200), nullable=False),
        sa.Column("faculty", sa.String(200), nullable=False),
        sa.Column("course", sa.String(200), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_students_score"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_students_faculty", "students", ["faculty"])
    op.create_index("ix_students_course", "students", ["course"])
    op.create_table(
        "csv_imports",
        sa.Column("checksum", sa.String(64), primary_key=True),
        sa.Column("records_count", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("csv_imports")
    op.drop_index("ix_students_course", table_name="students")
    op.drop_index("ix_students_faculty", table_name="students")
    op.drop_table("students")
