from typing import List, Literal, Optional

from pydantic import BaseModel, Field

LANG = r"^[a-z]{2,3}$"


class SessionCreate(BaseModel):
    patient_language: str = Field(default="hi", pattern=LANG)
    doctor_language: str = Field(default="en", pattern=LANG)
    consent: bool


class PrescriptionItem(BaseModel):
    drug: str = Field(min_length=2, max_length=80)
    dose: str = Field(default="", max_length=60)
    pattern: Optional[str] = Field(default=None, pattern=r"^\d(-\d){0,3}$")
    frequency_per_day: Optional[int] = Field(default=None, ge=1, le=4)
    days: Optional[int] = Field(default=None, ge=1, le=365)
    timing: Optional[Literal["before_food", "after_food", "with_food", "empty_stomach"]] = None


class PrescriptionRequest(BaseModel):
    prescriber_confirmed: bool
    items: List[PrescriptionItem] = Field(min_length=1, max_length=15)


class ResolveRequest(BaseModel):
    spoken: str = Field(min_length=2, max_length=80)
