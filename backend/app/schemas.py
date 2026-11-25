"""Every request schema (Pydantic) in one place, so validation is consistent across routers."""
import re
from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PhoneIn(BaseModel):
    phone: str = Field(pattern=r"^[6-9]\d{9}$")


class LoginIn(PhoneIn):
    otp: str = Field(min_length=6, max_length=6)


class SignupIn(LoginIn):
    name: str = Field(min_length=2, max_length=80)
    dob: date
    gender: Literal["Male", "Female", "Other"]
    city: str = Field(min_length=2, max_length=60)
    income_range: str
    interests: List[str] = []
    src: Optional[str] = None
    ref: Optional[str] = None
    first_src: Optional[str] = None
    how_heard_source_id: Optional[int] = None
    referrer_phone: Optional[str] = None


class AdminLogin(BaseModel):
    email: str
    password: str


class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    type: str = Field(min_length=2, max_length=30)


class StageIn(BaseModel):
    stage: Literal["Lead", "Fit", "Completed", "Failed"]
    failure_reason: Optional[str] = None
    survey_id: Optional[int] = None
    quality_check_passed: bool = True  # used when stage = Completed


class RuleIn(BaseModel):
    rule_type: Literal["age", "city", "gender", "income"]
    value: str = Field(min_length=1, max_length=200)
    strict_or_flexible: Literal["strict", "flexible"] = "strict"

    @field_validator("value")
    @classmethod
    def _v(cls, v, info):
        v = v.strip()
        if info.data.get("rule_type") == "age":
            m = re.fullmatch(r"(\d{1,3})\s*-\s*(\d{1,3})", v)
            if not m or int(m[1]) > int(m[2]):
                raise ValueError("Age rule must look like 18-35 (minimum first)")
            return f"{int(m[1])}-{int(m[2])}"
        return v


class SurveyIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = ""
    deadline: Optional[datetime] = None
    quota: Optional[int] = None
    amount: float = 0
    rules: List[RuleIn] = []


class MetaLeadIn(BaseModel):
    lead_id: str = Field(min_length=1)
    form_id: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_id: Optional[str] = None
    time: Optional[str] = None
    fields: Any = None


class FlagReviewIn(BaseModel):
    status: Literal["Cleared", "Confirmed"]
    note: Optional[str] = Field(default=None, max_length=300)


class OverrideIn(BaseModel):
    member_id: int
    survey_id: int
    reason: str = Field(min_length=3, max_length=300)


class PayoutStatusIn(BaseModel):
    status: Literal["Approved", "Paid"]
