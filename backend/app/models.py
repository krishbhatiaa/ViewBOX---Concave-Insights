import os
from datetime import datetime
from sqlalchemy import (create_engine, event, Column, Integer, String, DateTime, Date, Boolean, Text,
                        ForeignKey, Numeric, UniqueConstraint)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./viewbox.db"), connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
now = datetime.utcnow
FK = lambda t: Column(Integer, ForeignKey(t))

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True); name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False); unique_slug = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=now)

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True); phone = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False); dob = Column(Date); gender = Column(String); city = Column(String)
    income_range = Column(String); interests = Column(String, default="")
    source_id = FK("sources.id"); referrer_id = FK("members.id"); first_touch_source_id = FK("sources.id")
    created_at = Column(DateTime, default=now); is_flagged = Column(Boolean, default=False)
    ip = Column(String); device_id = Column(String)
    source = relationship("Source", foreign_keys=[source_id])
    referrer = relationship("Member", remote_side=[id])

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True); title = Column(String, nullable=False); description = Column(Text, default="")
    status = Column(String, default="live"); deadline = Column(DateTime); quota = Column(Integer)
    amount = Column(Numeric(10, 2), default=0); created_at = Column(DateTime, default=now)
    rules = relationship("SurveyRule", cascade="all, delete-orphan")

class SurveyRule(Base):
    __tablename__ = "survey_rules"
    id = Column(Integer, primary_key=True); survey_id = FK("surveys.id")
    rule_type = Column(String); operator = Column(String); value = Column(String); strict_or_flexible = Column(String, default="strict")

class EligibilityResult(Base):
    __tablename__ = "eligibility_results"
    __table_args__ = (UniqueConstraint("member_id", "survey_id", name="uq_elig_member_survey"),)
    id = Column(Integer, primary_key=True); member_id = FK("members.id"); survey_id = FK("surveys.id")
    result = Column(String); reason_text = Column(Text); computed_at = Column(DateTime, default=now)

class Referral(Base):
    __tablename__ = "referrals"
    id = Column(Integer, primary_key=True); referrer_id = FK("members.id"); referred_member_id = Column(Integer, ForeignKey("members.id"), unique=True)
    stage = Column(String, default="Lead"); failure_reason = Column(Text); updated_at = Column(DateTime, default=now)
    referred = relationship("Member", foreign_keys=[referred_member_id])

class Completion(Base):
    __tablename__ = "completions"
    id = Column(Integer, primary_key=True); member_id = FK("members.id"); survey_id = FK("surveys.id")
    completed_at = Column(DateTime, default=now); quality_check_passed = Column(Boolean, default=False)

class Payout(Base):
    __tablename__ = "payouts"
    id = Column(Integer, primary_key=True); member_id = FK("members.id"); survey_id = FK("surveys.id"); referral_id = FK("referrals.id")
    amount = Column(Numeric(10, 2)); status = Column(String, default="Pending"); approved_by = Column(String); approved_at = Column(DateTime)

class ImportLog(Base):
    __tablename__ = "import_logs"
    id = Column(Integer, primary_key=True); filename = Column(String); total_rows = Column(Integer)
    fixed_count = Column(Integer); skipped_count = Column(Integer); error_details_json = Column(Text); created_at = Column(DateTime, default=now)

class MetaLead(Base):
    __tablename__ = "meta_leads"
    id = Column(Integer, primary_key=True); lead_id = Column(String, unique=True, nullable=False); form_id = Column(String)
    campaign_id = Column(String); ad_id = Column(String); received_at = Column(DateTime, default=now)
    raw_payload_json = Column(Text); member_id = FK("members.id")

class AdminOverride(Base):
    __tablename__ = "admin_overrides"
    __table_args__ = (UniqueConstraint("member_id", "survey_id", name="uq_override_member_survey"),)
    id = Column(Integer, primary_key=True); member_id = FK("members.id"); survey_id = FK("surveys.id")
    overridden_by = Column(String); reason = Column(Text); created_at = Column(DateTime, default=now)

class FraudFlag(Base):
    __tablename__ = "fraud_flags"
    id = Column(Integer, primary_key=True); member_id = FK("members.id"); flag_type = Column(String)
    details = Column(Text); status = Column(String, default="open"); created_at = Column(DateTime, default=now)
    reviewed_by = Column(String); reviewed_at = Column(DateTime)

class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True); email = Column(String, unique=True); password_hash = Column(String); created_at = Column(DateTime, default=now)
