"""Every request schema (Pydantic) in one place, so validation is consistent across routers."""
import re
from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


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
    ch: Optional[str] = Field(default=None, max_length=30)


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


class SurveyPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[Literal["draft", "live", "closed"]] = None
    deadline: Optional[datetime] = None
    quota: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = Field(default=None, ge=0)

    @field_validator("deadline")
    @classmethod
    def _future(cls, v):
        if v is not None and v <= datetime.utcnow():
            raise ValueError("deadline must be in the future")
        return v


class GridFilterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(default="", max_length=100)
    source_id: Optional[int] = None
    city: str = Field(default="", max_length=60)
    status: str = Field(default="", max_length=30)
    survey_id: Optional[int] = None


class SuggestRulesIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)


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


# Admin grid/export keeps full phone where operations explicitly needs it; member schemas mask it.
class _PhoneMasked(BaseModel):
    phone: str

    @field_serializer("phone")
    def _mask_phone(self, value: str) -> str:
        return value[:2] + "X" * 6 + value[-2:] if value and len(value) >= 4 else "XXXX"


class MeOut(_PhoneMasked):
    id: int
    name: str
    city: Optional[str] = None
    interests: List[str] = []
    next_eligible_date: Optional[str] = None
    referral_link: str


class SurveyOut(BaseModel):
    id: int
    title: str
    description: str
    deadline: Optional[datetime] = None
    amount: float
    matches_interests: bool
    result: str
    reason: Optional[str] = None


class CompletionOut(BaseModel):
    survey: str
    completed_at: date
    quality_passed: bool


class PayoutOut(BaseModel):
    kind: str
    amount: float
    status: str


class StatusOut(BaseModel):
    stage: str
    failure_reason: Optional[str] = None
    completions: List[CompletionOut] = []
    payouts: List[PayoutOut] = []


class BonusOut(BaseModel):
    amount: float
    status: str


class ReferralOut(_PhoneMasked):
    bonus: Optional[BonusOut] = None
    friend: str
    stage: str
    failure_reason: Optional[str] = None
    updated_at: datetime
