from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class StudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_name: Text
    first_name: Text
    faculty: Text
    course: Text
    score: int = Field(strict=True, ge=0, le=100)


class StudentRead(StudentCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class FacultyAverage(BaseModel):
    faculty: str
    average_score: float
    records_count: int


class ImportResult(BaseModel):
    imported: int
    already_imported: bool
