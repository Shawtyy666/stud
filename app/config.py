import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "students.csv"


def database_url() -> str:
    return os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'students.db').as_posix()}")
