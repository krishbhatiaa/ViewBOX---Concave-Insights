import csv, io, json, logging, os, re
from datetime import date, datetime
from typing import Any, List, Literal, Optional
from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from . import security as sec
from . import fraud
from .eligibility import evaluate, next_eligible_date
from .models import *

log = logging.getLogger("viewbox")
# CORS: FRONTEND_URL may be comma-separated (e.g. Vite dev server + built app)
_origins = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:8000").split(",") if o.strip()]
_origins += ["http://localhost:5173", "http://127.0.0.1:5173"]
app = FastAPI(title="ViewBox Panel System")
app.add_middleware(CORSMiddleware, allow_origins=list(dict.fromkeys(_origins)), allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)

def _ensure_columns():
    """SQLite has no ALTER COLUMN: add columns introduced after a table was created."""
    from sqlalchemy import inspect, text
    want = {"members": {"ip": "VARCHAR", "device_id": "VARCHAR"},
            "fraud_flags": {"reviewed_by": "VARCHAR", "reviewed_at": "DATETIME"}}
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in want.items():
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, typ in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
_ensure_columns()

@app.exception_handler(Exception)
async def friendly(_, exc):
    log.exception("unhandled"); return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, 500)

def db_dep():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def auth(role):
    def dep(authorization: str = Header(None)):
        t = sec.read_token((authorization or "").replace("Bearer ", ""))
        if not t or t["role"] != role: raise HTTPException(401, "Please log in again.")
        return t
    return dep
member_auth, admin_auth = auth("member"), auth("admin")

def slugify(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def norm_phone(p):
    d = re.sub(r"\D", "", str(p or ""))[-10:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else None
def base_url(request: Request) -> str:
    """Origin the caller actually used (works behind Vite proxy and in production)."""
    return str(request.base_url).rstrip("/")
def link_for(src, request: Request): return f"{base_url(request)}/signup?src={sec.sign_link('src', src.unique_slug)}"

# ---------- schemas ----------
class PhoneIn(BaseModel): phone: str = Field(pattern=r"^[6-9]\d{9}$")
class LoginIn(PhoneIn): otp: str = Field(min_length=6, max_length=6)
class SignupIn(LoginIn):
    name: str = Field(min_length=2, max_length=80); dob: date
    gender: Literal["Male", "Female", "Other"]; city: str = Field(min_length=2, max_length=60)
    income_range: str; interests: List[str] = []
    src: Optional[str] = None; ref: Optional[str] = None; first_src: Optional[str] = None
    how_heard_source_id: Optional[int] = None; referrer_phone: Optional[str] = None
class AdminLogin(BaseModel): email: str; password: str
class SourceIn(BaseModel): name: str = Field(min_length=2, max_length=60); type: str = Field(min_length=2, max_length=30)
class StageIn(BaseModel):
    stage: Literal["Lead", "Fit", "Completed", "Failed"]; failure_reason: Optional[str] = None
    survey_id: Optional[int] = None; quality_check_passed: bool = True  # used when stage = Completed
class RuleIn(BaseModel):
    rule_type: Literal["age", "city", "gender", "income"]; value: str = Field(min_length=1, max_length=200); strict_or_flexible: Literal["strict", "flexible"] = "strict"
    @field_validator("value")
    @classmethod
    def _v(cls, v, info):
        v = v.strip()
        if info.data.get("rule_type") == "age":
            m = re.fullmatch(r"(\d{1,3})\s*-\s*(\d{1,3})", v)
            if not m or int(m[1]) > int(m[2]): raise ValueError("Age rule must look like 18-35 (minimum first)")
            return f"{int(m[1])}-{int(m[2])}"
        return v
class SurveyIn(BaseModel):
    title: str = Field(min_length=3, max_length=120); description: str = ""; deadline: Optional[datetime] = None; quota: Optional[int] = None
    amount: float = 0; rules: List[RuleIn] = []
class MetaLeadIn(BaseModel):
    lead_id: str = Field(min_length=1); form_id: Optional[str] = None; campaign_id: Optional[str] = None
    ad_id: Optional[str] = None; time: Optional[str] = None; fields: Any = None
class FlagReviewIn(BaseModel):
    status: Literal["Cleared", "Confirmed"]; note: Optional[str] = Field(default=None, max_length=300)
class OverrideIn(BaseModel):
    member_id: int; survey_id: int; reason: str = Field(min_length=3, max_length=300)

# ---------- member auth ----------
@app.post("/api/otp/request")
def otp_request(b: PhoneIn, db: Session = Depends(db_dep)):
    """Mock OTP: returned in the response and shown on screen. No SMS."""
    return {"otp": sec.issue_otp(b.phone), "is_member": bool(db.query(Member).filter_by(phone=b.phone).first())}

@app.post("/api/login")
def login(b: LoginIn, db: Session = Depends(db_dep)):
    m = db.query(Member).filter_by(phone=b.phone).first()
    if not m: raise HTTPException(404, "No account for this number yet. Please sign up.")
    sec.check_otp(b.phone, b.otp)
    return {"token": sec.make_token(m.id, "member")}

@app.post("/api/signup")
def signup(b: SignupIn, request: Request, x_device_id: str = Header(None), db: Session = Depends(db_dep)):
    sec.check_otp(b.phone, b.otp)  # verify first so unauthenticated callers can't spam flags
    existing = db.query(Member).filter_by(phone=b.phone).first()
    if existing:
        fraud.add_flag(db, existing.id, "duplicate_signup",
                       f"Another sign-up attempt with this phone at {datetime.utcnow():%Y-%m-%d %H:%M} UTC.")
        db.commit()
        raise HTTPException(409, "This number is already registered. Please log in.")
    src = referrer = None; notes = []
    if b.src:
        slug = sec.verify_link("src", b.src)
        src = db.query(Source).filter_by(unique_slug=slug).first() if slug else None
        if not src: notes.append("Source link could not be verified and was ignored.")
    if b.ref:
        rid = sec.verify_link("ref", b.ref)
        referrer = db.get(Member, int(rid)) if rid and rid.isdigit() else None
        if not referrer: notes.append("Referral link could not be verified and was ignored.")
    if not referrer and b.referrer_phone:  # typed referrer: matched by exact phone, never by ambiguous name
        referrer = db.query(Member).filter_by(phone=norm_phone(b.referrer_phone) or "-").first()
        if not referrer or referrer.phone == b.phone: referrer = None; notes.append("We couldn't find a member with that referrer number.")
    first = None; fslug = sec.verify_link("src", b.first_src) if b.first_src else None
    if fslug: first = db.query(Source).filter_by(unique_slug=fslug).first()
    if not src and referrer: src = db.query(Source).filter_by(type="referral").first()  # ref only -> source=Referral
    if not src and b.how_heard_source_id: src = db.get(Source, b.how_heard_source_id)
    ip = ((request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else None))
    m = Member(phone=b.phone, name=b.name.strip(), dob=b.dob, gender=b.gender, city=b.city.strip().title(), income_range=b.income_range,
               interests=",".join(b.interests), source_id=src and src.id, first_touch_source_id=(first or src) and (first or src).id,
               referrer_id=referrer and referrer.id, ip=ip or None, device_id=x_device_id)
    db.add(m); db.flush(); db.add(Referral(referrer_id=m.referrer_id, referred_member_id=m.id))
    fraud.on_signup(db, m, referrer, m.ip, m.device_id)
    db.commit()
    return {"token": sec.make_token(m.id, "member"), "notes": notes}

@app.get("/api/links/resolve")
def resolve_links(src: str = "", ref: str = "", db: Session = Depends(db_dep)):
    """Lets the signup page greet the visitor and decide whether to show 'How did you hear about us?'."""
    slug = sec.verify_link("src", src) if src else None
    s = db.query(Source).filter_by(unique_slug=slug).first() if slug else None
    rid = sec.verify_link("ref", ref) if ref else None
    r = db.get(Member, int(rid)) if rid and rid.isdigit() else None
    return {"source": s and s.name, "referrer": r and r.name.split()[0], "needs_fallback": not s and not r}

@app.get("/api/sources/public")
def public_sources(db: Session = Depends(db_dep)):
    return [{"id": s.id, "name": s.name} for s in db.query(Source).order_by(Source.name)]

# ---------- member portal ----------
def me(t, db):
    m = db.get(Member, t["sub"])
    if not m: raise HTTPException(401, "Please log in again.")
    return m

@app.get("/api/me")
def get_me(request: Request, t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db); d = next_eligible_date(db, m)
    return {"id": m.id, "name": m.name, "phone": sec.mask(m.phone), "city": m.city, "interests": [i for i in (m.interests or "").split(",") if i],
            "next_eligible_date": d and d.isoformat(), "referral_link": f"{base_url(request)}/signup?ref={sec.sign_link('ref', str(m.id))}"}

@app.get("/api/surveys")
def surveys(t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db); ints = [i for i in (m.interests or "").split(",") if i]; out = []
    for s in db.query(Survey).filter_by(status="live"):
        res, why = evaluate(db, m, s); record_result(db, m.id, s.id, res, why)
        text = (s.title + " " + s.description).lower()
        out.append({"id": s.id, "title": s.title, "description": s.description, "deadline": s.deadline and s.deadline.isoformat(), "amount": s.amount,
                    "matches_interests": any(i.lower() in text for i in ints), "result": res, "reason": why})
    db.commit()  # every computed result lands in eligibility_results
    return sorted(out, key=lambda x: not x["matches_interests"])

@app.get("/api/me/status")
def my_status(t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db); r = db.query(Referral).filter_by(referred_member_id=m.id).first()
    comps = []
    for c in db.query(Completion).filter_by(member_id=m.id):
        sv = db.get(Survey, c.survey_id) if c.survey_id else None
        comps.append({"survey": sv.title if sv else "Completed before joining (imported)",
                      "completed_at": c.completed_at.date().isoformat(), "quality_passed": c.quality_check_passed})
    return {"stage": r.stage if r else "Lead", "failure_reason": r.failure_reason if r else None,
            "completions": comps,
            "payouts": [{"kind": "Referral bonus" if p.referral_id else "Survey payment", "amount": p.amount, "status": p.status} for p in db.query(Payout).filter_by(member_id=m.id)]}

@app.get("/api/me/referrals")
def my_referrals(t=Depends(member_auth), db: Session = Depends(db_dep)):
    rows = db.query(Referral).filter_by(referrer_id=t["sub"]).all()
    bonus = {p.referral_id: p for p in db.query(Payout).filter(Payout.member_id == t["sub"], Payout.referral_id != None)}
    return [{"bonus": {"amount": bonus[r.id].amount, "status": bonus[r.id].status} if r.id in bonus else None, "friend": r.referred.name, "phone": sec.mask(r.referred.phone), "stage": r.stage, "failure_reason": r.failure_reason, "updated_at": r.updated_at.isoformat()} for r in rows]

# ---------- admin ----------
@app.post("/api/admin/login")
def admin_login(b: AdminLogin, db: Session = Depends(db_dep)):
    a = db.query(AdminUser).filter_by(email=b.email.lower()).first()
    if not a or not sec.check_pw(b.password, a.password_hash): raise HTTPException(401, "Incorrect email or password.")
    return {"token": sec.make_token(a.email, "admin")}

@app.get("/api/admin/sources")
def list_sources(request: Request, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": s.id, "name": s.name, "type": s.type, "link": link_for(s, request)} for s in db.query(Source).order_by(Source.name)]

@app.post("/api/admin/sources", status_code=201)
def add_source(b: SourceIn, request: Request, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    if db.query(Source).filter_by(name=b.name).first(): raise HTTPException(409, "A source with this name already exists.")
    base = slugify(b.name) or "source"; slug, n = base, 2
    while db.query(Source).filter_by(unique_slug=slug).first(): slug, n = f"{base}-{n}", n + 1
    s = Source(name=b.name, type=slugify(b.type) or "other", unique_slug=slug); db.add(s); db.commit()
    return {"id": s.id, "name": s.name, "type": s.type, "link": link_for(s, request)}

@app.post("/api/admin/surveys", status_code=201)
def add_survey(b: SurveyIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    s = Survey(**b.model_dump(exclude={"rules"}), rules=[SurveyRule(**r.model_dump(), operator="between" if r.rule_type == "age" else "in") for r in b.rules]); db.add(s); db.commit()
    return {"id": s.id}

ELIGIBILITY_STATUSES = ("Approved", "Rejected", "Waitlisted")  # per-survey results (need survey_id)
STAGE_STATUSES = ("Lead", "Fit", "Completed", "Failed", "flagged")

def record_result(db, member_id, survey_id, result, reason):
    """Persist a computed eligibility result: one row per member+survey, updated in place."""
    row = db.query(EligibilityResult).filter_by(member_id=member_id, survey_id=survey_id).first()
    if row is None:
        db.add(EligibilityResult(member_id=member_id, survey_id=survey_id, result=result, reason_text=reason))
    else:
        row.result, row.reason_text, row.computed_at = result, reason, datetime.utcnow()
    return result, reason

def member_query(db, q, source_id, city, status):
    qs = db.query(Member)
    if q:
        conds = [Member.name.ilike(f"%{q}%"), Member.city.ilike(f"%{q}%")]
        if q.isdigit(): conds.append(Member.id == int(q))
        qs = qs.filter(or_(*conds))
    if source_id: qs = qs.filter(Member.source_id == source_id)
    if city: qs = qs.filter(Member.city.ilike(city))
    if status == "flagged": qs = qs.filter(Member.is_flagged == True)
    elif status in ("Lead", "Fit", "Completed", "Failed"):
        qs = qs.filter(Member.id.in_(db.query(Referral.referred_member_id).filter(Referral.stage == status)))
    return qs.order_by(Member.id)

def grid_rows(db, q="", source_id=None, city="", status="", survey_id=None):
    """Grid rows for the current search/filter view.

    When survey_id is given, every candidate member is evaluated against that survey,
    the result is saved to eligibility_results and returned as `eligibility`;
    status=Approved|Rejected|Waitlisted then narrows the view to that result.
    """
    survey = None
    if survey_id:
        survey = db.get(Survey, survey_id)
        if not survey: raise HTTPException(404, "Survey not found.")
        if status and status not in ELIGIBILITY_STATUSES and status not in STAGE_STATUSES:
            raise HTTPException(422, f"Unknown status '{status}'.")
    elif status in ELIGIBILITY_STATUSES:
        raise HTTPException(422, "Choose a survey first to filter by Approved / Rejected / Waitlisted.")
    stage_status = status if status in STAGE_STATUSES else ""
    stage = {r.referred_member_id: r for r in db.query(Referral)}
    out = []
    for m in member_query(db, q=q, source_id=source_id, city=city, status=stage_status):
        row = {"id": m.id, "referral_id": stage[m.id].id if m.id in stage else None, "name": m.name, "phone": m.phone,
               "city": m.city, "gender": m.gender, "source": m.source.name if m.source else "Unknown",
               "referrer": m.referrer.name if m.referrer else "",
               "stage": stage[m.id].stage if m.id in stage else "Lead", "created_at": m.created_at.date().isoformat()}
        if survey:
            res, why = evaluate(db, m, survey)
            record_result(db, m.id, survey.id, res, why)  # saved so the grid/audit can read it later
            row["eligibility"] = {"result": res, "reason": why}
            if status in ELIGIBILITY_STATUSES and res != status: continue
        out.append(row)
    if survey: db.commit()  # persist every computed result in one go
    return out

@app.get("/api/admin/members")
def admin_members(q: str = "", source_id: Optional[int] = None, city: str = "", status: str = "",
                  survey_id: Optional[int] = None, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return grid_rows(db, q=q, source_id=source_id, city=city, status=status, survey_id=survey_id)

GRID_FIELDS = ["id", "name", "phone", "city", "gender", "source", "referrer", "stage", "created_at", "eligibility", "eligibility_reason"]

@app.get("/api/admin/members/export")
def export(q: str = "", source_id: Optional[int] = None, city: str = "", status: str = "",
           survey_id: Optional[int] = None, format: str = Query("csv", pattern="^(csv|xlsx)$"),
           _=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Download the current grid view as CSV or Excel (.xlsx)."""
    rows = grid_rows(db, q=q, source_id=source_id, city=city, status=status, survey_id=survey_id)
    for r in rows:  # flatten eligibility for the spreadsheet
        e = r.pop("eligibility", None) or {}
        r["eligibility"] = e.get("result", "")
        r["eligibility_reason"] = e.get("reason", "")
    fields = GRID_FIELDS if survey_id else [f for f in GRID_FIELDS if f not in ("eligibility", "eligibility_reason")]
    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Members"
        ws.append(fields)
        for r in rows: ws.append([r.get(k, "") for k in fields])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=members.xlsx"})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=members.csv"})

BONUS = float(os.getenv("REFERRAL_BONUS", "100"))

@app.get("/api/admin/surveys")
def admin_surveys(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": x.id, "title": x.title, "status": x.status, "deadline": x.deadline and x.deadline.date().isoformat(), "quota": x.quota, "amount": x.amount,
             "completions": db.query(Completion).filter_by(survey_id=x.id).count(),
             "rules": [{"rule_type": r.rule_type, "value": r.value, "strict_or_flexible": r.strict_or_flexible} for r in x.rules]} for x in db.query(Survey).order_by(Survey.id.desc())]

@app.post("/api/admin/referrals/{rid}/stage")
def set_stage(rid: int, b: StageIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    r = db.get(Referral, rid)
    if not r: raise HTTPException(404, "Referral not found.")
    if r.stage == "Completed" and b.stage != "Completed": raise HTTPException(409, "This member already completed a survey, so the stage can't be changed.")
    reason = b.failure_reason
    if b.stage == "Failed" and not reason: raise HTTPException(422, "Please give a reason when marking Failed.")
    if b.stage == "Completed":
        sv = db.get(Survey, b.survey_id) if b.survey_id else None
        if not sv: raise HTTPException(422, "Please choose which survey was completed.")
        if db.query(Completion).filter_by(member_id=r.referred_member_id, survey_id=sv.id).first(): raise HTTPException(409, "This completion is already recorded.")
        db.add(Completion(member_id=r.referred_member_id, survey_id=sv.id, quality_check_passed=b.quality_check_passed))  # starts the 3-month cool-off when quality passed
        if b.quality_check_passed:
            db.add(Payout(member_id=r.referred_member_id, survey_id=sv.id, amount=sv.amount))
            if r.referrer_id and not db.query(Payout).filter_by(referral_id=r.id).first():
                db.add(Payout(member_id=r.referrer_id, survey_id=sv.id, referral_id=r.id, amount=BONUS))
        else: b.stage, reason = "Failed", "Did not pass the quality check, so no payment is due."
    r.stage, r.failure_reason, r.updated_at = b.stage, reason if b.stage == "Failed" else None, datetime.utcnow(); db.commit()
    return {"ok": True, "stage": r.stage}

class PayoutStatusIn(BaseModel):
    status: Literal["Approved", "Paid"]

@app.get("/api/admin/payouts")
def payouts(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": p.id, "member": db.get(Member, p.member_id).name, "kind": "Referral bonus" if p.referral_id else "Survey payment", "amount": p.amount, "status": p.status} for p in db.query(Payout).order_by(Payout.id.desc())]

@app.post("/api/admin/payouts/{pid}/status")
def payout_status(pid: int, b: Optional[PayoutStatusIn] = Body(None),
                  status: Optional[Literal["Approved", "Paid"]] = Query(None),
                  t=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Accepts the status as JSON body (frontend) or query string (README examples)."""
    val = (b and b.status) or status
    if not val: raise HTTPException(422, "Please give a status of Approved or Paid.")
    p = db.get(Payout, pid)
    if not p: raise HTTPException(404, "Payout not found.")
    if val == "Paid" and p.status != "Approved": raise HTTPException(409, "Ops must approve a payout before it can be marked Paid.")
    p.status = val
    if val == "Approved": p.approved_by, p.approved_at = t["sub"], datetime.utcnow()
    db.commit(); return {"ok": True}

@app.get("/api/admin/source-stats")
def source_stats(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    out = []
    for s in db.query(Source):
        st = [r.stage for r in db.query(Referral).join(Member, Member.id == Referral.referred_member_id).filter(Member.source_id == s.id)]
        out.append({"source": s.name, "type": s.type, "signups": len(st), "fit": sum(x in ("Fit", "Completed") for x in st), "completed": st.count("Completed")})
    return sorted(out, key=lambda x: -x["signups"])

# ---------- fraud review queue ----------
@app.get("/api/admin/fraud-flags")
def fraud_flags(status: str = "open", _=Depends(admin_auth), db: Session = Depends(db_dep)):
    q = db.query(FraudFlag)
    if status != "all": q = q.filter_by(status=status)
    out = []
    for f in q.order_by(FraudFlag.id.desc()):
        m = db.get(Member, f.member_id)
        out.append({"id": f.id, "member_id": f.member_id, "name": m.name if m else "(deleted member)",
                    "phone": m.phone if m else "", "flag_type": f.flag_type, "details": f.details,
                    "status": f.status, "created_at": f.created_at.date().isoformat(),
                    "reviewed_by": f.reviewed_by})
    return out

@app.post("/api/admin/fraud-flags/{fid}/review")
def review_flag(fid: int, b: FlagReviewIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    f = db.get(FraudFlag, fid)
    if not f: raise HTTPException(404, "Flag not found.")
    f.status = b.status  # Cleared or Confirmed — rows are never deleted
    if b.note: f.details = f"{f.details} · Review note: {b.note}"
    f.reviewed_by, f.reviewed_at = t["sub"], datetime.utcnow()
    db.flush()  # autoflush is off; flush so the open-count below sees the new status
    open_left = db.query(FraudFlag).filter_by(member_id=f.member_id, status="open").count()
    m = db.get(Member, f.member_id)
    if m: m.is_flagged = open_left > 0
    db.commit()
    return {"ok": True, "status": f.status, "member_flagged": bool(m and m.is_flagged)}

@app.post("/api/admin/fraud/scan")
def fraud_scan(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Re-check everyone for device/IP bursts and referral rings."""
    return {"flags_created": fraud.scan(db)}

# ---------- manual eligibility override ----------
@app.get("/api/admin/overrides")
def list_overrides(member_id: Optional[int] = None, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    q = db.query(AdminOverride)
    if member_id: q = q.filter_by(member_id=member_id)
    return [{"id": o.id, "member_id": o.member_id, "member": db.get(Member, o.member_id).name,
             "survey_id": o.survey_id, "survey": db.get(Survey, o.survey_id).title,
             "reason": o.reason, "created_at": o.created_at.date().isoformat()} for o in q.order_by(AdminOverride.id.desc())]

@app.post("/api/admin/overrides", status_code=201)
def create_override(b: OverrideIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    if not db.get(Member, b.member_id): raise HTTPException(404, "Member not found.")
    if not db.get(Survey, b.survey_id): raise HTTPException(404, "Survey not found.")
    if db.query(AdminOverride).filter_by(member_id=b.member_id, survey_id=b.survey_id).first():
        raise HTTPException(409, "An override already exists for this member and survey.")
    db.add(AdminOverride(member_id=b.member_id, survey_id=b.survey_id, overridden_by=t["sub"], reason=b.reason.strip()))
    db.commit()
    return {"ok": True}

@app.delete("/api/admin/overrides/{oid}")
def delete_override(oid: int, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    o = db.get(AdminOverride, oid)
    if not o: raise HTTPException(404, "Override not found.")
    db.delete(o); db.commit()
    return {"ok": True}

# ---------- messy CSV import ----------
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%Y/%m/%d", "%m/%d/%Y")

def parse_date(v, floor=1920):
    """Read the date formats seen in messy exports (ISO, dd/mm/yyyy, dd-mm-yy, ...).

    Two-digit years pivot around today ('68' -> 1968, '25' -> 2025); impossible or future
    dates return None so the caller reports the row instead of guessing.
    """
    s = str(v or "").strip()
    if not s: return None
    today = date.today()
    for f in DATE_FORMATS:
        try: d = datetime.strptime(s, f).date()
        except ValueError: continue
        if "%y" in f and d.year > today.year: d = d.replace(year=d.year - 100)
        if floor < d.year <= today.year: return d
    return None

INCOME_BUCKETS = {  # messy export values -> the three buckets the profile form offers
    "below 3l": "<5L", "below 5l": "<5L", "<5l": "<5L", "0-5l": "<5L", "under 5l": "<5L",
    "3l-6l": "5-10L", "3-6l": "5-10L", "5-10l": "5-10L", "6l-10l": "5-10L", "5 lakh": "5-10L",
    "10l-20l": "10L+", "10l+": "10L+", "above 10l": "10L+", "above 20l": "10L+", "20l+": "10L+",
}

def norm_income(v):
    """-> (value, note, level): level 'fix' when we mapped it, 'warn' when we could not."""
    s = str(v or "").strip()
    if not s: return None, "no income in this row", "warn"
    hit = INCOME_BUCKETS.get(s.lower())
    if hit:
        return (hit, None, "fix") if hit.lower() == s.lower() else (hit, f"income '{s}' mapped to '{hit}'", "fix")
    return s, f"income '{s}' kept as written (profile options are <5L, 5-10L, 10L+)", "warn"

def _plan_import_row(raw, srcs, seen):
    """Validate + normalise one CSV row without touching the database.

    Returns (plan, fixes, warns). Raises ValueError with a human reason to skip the row.
    """
    r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
    fixes, warns = [], []
    phone = norm_phone(r.get("phone") or r.get("mobile"))
    if not phone: raise ValueError("invalid or missing phone")
    if phone in seen: raise ValueError("duplicate phone")
    name = " ".join((r.get("name") or "").split()).title()
    if len(name) < 2: raise ValueError("missing name")
    raw_dob = r.get("dob") or r.get("date_of_birth") or ""
    dob = parse_date(raw_dob)
    if raw_dob and not dob: warns.append(f"date of birth '{raw_dob}' could not be read")
    g_raw = r.get("gender") or ""
    g = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}.get(g_raw.lower()) or ("Other" if g_raw else None)
    if g_raw and g != g_raw: fixes.append(f"gender '{g_raw}' -> {g}")
    if not g_raw: warns.append("no gender in this row")
    if (r.get("phone") or "") != phone: fixes.append("phone normalised")
    city_raw = r.get("city") or ""
    city = city_raw.title() if city_raw and (city_raw.islower() or city_raw.isupper()) else city_raw
    if city != city_raw: fixes.append(f"city '{city_raw}' -> {city}")
    income, note, level = norm_income(r.get("income") or r.get("income_range"))
    if note: (fixes if level == "fix" else warns).append(note)
    src_name = r.get("source") or ""
    if "source" in r and not src_name: warns.append("no source in this row - the member will show as Unknown")
    elif src_name and not srcs.get(src_name.lower()): warns.append(f"source '{src_name}' is not set up yet - it will be created")
    raw_joined = r.get("joined_on") or ""
    joined = parse_date(raw_joined)
    if raw_joined and not joined: warns.append(f"join date '{raw_joined}' could not be read - using today")
    raw_done = r.get("last_survey_completed_on") or ""
    done = parse_date(raw_done)
    if raw_done and not done: warns.append(f"last survey date '{raw_done}' could not be read - no cool-off recorded")
    plan = {"phone": phone, "name": name, "dob": dob, "gender": g, "city": city or None,
            "income_range": income, "interests": r.get("interests", "").replace(";", ","),
            "source": srcs.get(src_name.lower()), "source_name": src_name,
            "legacy_id": (r.get("member_id") or "").strip().upper() or None,
            "ref_by": (r.get("referred_by") or "").strip().upper() or None,
            "joined": joined, "completed": done}
    return plan, fixes, warns

@app.post("/api/admin/import")
async def import_csv(file: UploadFile = File(...), dry_run: bool = Query(False), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    try: text = (await file.read()).decode("utf-8-sig", errors="replace")
    except Exception: raise HTTPException(400, "Could not read this file.")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows: raise HTTPException(422, "The file has no data rows.")
    srcs = {s.name.lower(): s for s in db.query(Source)}; seen = {m.phone for m in db.query(Member.phone)}
    entries, planned = {}, []
    for i, raw in enumerate(rows, start=2):
        try:
            plan, fixes, warns = _plan_import_row(raw, srcs, seen)
            seen.add(plan["phone"]); planned.append((i, plan, fixes, warns))
        except Exception as e:
            entries[i] = {"row": i, "action": "skipped", "reason": str(e)[:120]}
    # referred_by carries legacy ids (VB10002): link referrers once every row is planned
    by_legacy, by_phone = {}, {}
    for _, plan, _, _ in planned:
        if plan["legacy_id"]: by_legacy.setdefault(plan["legacy_id"], plan)
        by_phone.setdefault(plan["phone"], plan)
    for _, plan, _, warns in planned:
        if not plan["ref_by"]: continue
        target = by_legacy.get(plan["ref_by"]) or by_phone.get(plan["ref_by"])
        if target is plan: warns.append("self-referral ignored")
        elif not target: warns.append(f"referrer '{plan['ref_by']}' was not imported - no referral credited")
        else: plan["referrer"] = target
    fixed = warned = 0
    for i, plan, fixes, warns in planned:
        if warns:
            warned += 1; entries[i] = {"row": i, "action": "warned", "reason": "; ".join(fixes + warns)[:400]}
        elif fixes:
            fixed += 1; entries[i] = {"row": i, "action": "fixed", "reason": "; ".join(fixes)[:400]}
    detail = [entries[k] for k in sorted(entries)]
    added = len(planned); skipped = len(rows) - added
    summary = {"total_rows": len(rows), "imported": added, "fixed": fixed, "warned": warned,
               "skipped": skipped, "details": detail}
    if dry_run:
        # Nothing has been written — validation only.
        return {"preview": True, **summary}
    for i, plan, fixes, warns in planned:
        s = plan["source"]
        if s is None and plan["source_name"]:  # sources are data: unknown names become real sources
            key = plan["source_name"].lower(); s = srcs.get(key)
            if s is None:
                base = slugify(plan["source_name"]) or "source"; slug, n = base, 2
                while db.query(Source).filter_by(unique_slug=slug).first(): slug, n = f"{base}-{n}", n + 1
                s = Source(name=plan["source_name"], type="imported", unique_slug=slug)
                db.add(s); db.flush(); srcs[key] = s
        m = Member(phone=plan["phone"], name=plan["name"], dob=plan["dob"], gender=plan["gender"],
                   city=plan["city"], income_range=plan["income_range"], interests=plan["interests"],
                   source_id=s and s.id, first_touch_source_id=s and s.id)
        if plan["joined"]: m.created_at = datetime.combine(plan["joined"], datetime.min.time())
        db.add(m); db.flush(); plan["_member"] = m
    for i, plan, fixes, warns in planned:
        m = plan["_member"]; ref = plan.get("referrer")
        ref_id = ref["_member"].id if ref is not None else None
        if ref_id and ref_id != m.id: m.referrer_id = ref_id
        db.add(Referral(referrer_id=ref_id if ref_id and ref_id != m.id else None, referred_member_id=m.id))
        if plan["completed"]:  # legacy completion history -> starts the 3-month cool-off
            db.add(Completion(member_id=m.id, survey_id=None,
                              completed_at=datetime.combine(plan["completed"], datetime.min.time()),
                              quality_check_passed=True))
    db.add(ImportLog(filename=file.filename, total_rows=len(rows), fixed_count=fixed, skipped_count=skipped,
                     error_details_json=json.dumps(detail)))
    db.commit()
    return summary

# ---------- Meta lead ads ----------
@app.post("/api/meta/lead")
def meta_lead(b: MetaLeadIn, db: Session = Depends(db_dep)):
    if db.query(MetaLead).filter_by(lead_id=b.lead_id).first(): return {"status": "duplicate", "lead_id": b.lead_id}
    f = b.fields
    if isinstance(f, list): f = {i.get("name"): (i.get("values") or [""])[0] for i in f if isinstance(i, dict)}
    f = f if isinstance(f, dict) else {}
    name, phone, city = f.get("name") or f.get("full_name"), norm_phone(f.get("phone") or f.get("phone_number")), f.get("city")
    lead = MetaLead(lead_id=b.lead_id, form_id=b.form_id, campaign_id=b.campaign_id, ad_id=b.ad_id, raw_payload_json=json.dumps(b.model_dump(), default=str))
    if not phone or not name or len(str(name).strip()) < 2:
        db.add(lead); db.commit()  # keep for review, never lose a lead
        raise HTTPException(422, "Lead rejected: a valid name and 10-digit Indian mobile number are required.")
    m = db.query(Member).filter_by(phone=phone).first(); status = "linked_existing"
    if not m:
        s = db.query(Source).filter_by(name="Meta Ads").first() or Source(name="Meta Ads", type="meta_ads", unique_slug="meta-ads")
        db.add(s); db.flush()
        m = Member(phone=phone, name=str(name).strip().title(), city=str(city or "").title() or None, source_id=s.id, first_touch_source_id=s.id)
        db.add(m); db.flush(); db.add(Referral(referred_member_id=m.id)); status = "created"
    lead.member_id = m.id; db.add(lead); db.commit()
    return {"status": status, "member_id": m.id, "source": "Meta Ads", "campaign_id": b.campaign_id}

# ---------- frontend (SPA: every non-API GET serves the built app, so deep links work) ----------
_DIST = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
_INDEX = os.path.join(_DIST, "index.html")
if not os.path.isfile(_INDEX):  # dev fallback: the Vite shell (served behind `npm run dev`)
    _INDEX = os.path.join(_DIST, "..", "index.html")

@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(404, "Not found.")
    candidate = os.path.normpath(os.path.join(_DIST, full_path))
    if (candidate == _DIST or candidate.startswith(_DIST + os.sep)) and os.path.isfile(candidate):  # hashed assets, favicon, etc.
        return FileResponse(candidate)
    return FileResponse(_INDEX)
