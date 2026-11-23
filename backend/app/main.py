import csv, io, json, logging, os, re
from datetime import date, datetime
from typing import Any, List, Literal, Optional
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from . import security as sec
from .eligibility import evaluate, next_eligible_date
from .models import *

log = logging.getLogger("viewbox")
# CORS: FRONTEND_URL may be comma-separated (e.g. Vite dev server + built app)
_origins = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:8000").split(",") if o.strip()]
_origins += ["http://localhost:5173", "http://127.0.0.1:5173"]
app = FastAPI(title="ViewBox Panel System")
app.add_middleware(CORSMiddleware, allow_origins=list(dict.fromkeys(_origins)), allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)

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
def signup(b: SignupIn, db: Session = Depends(db_dep)):
    if db.query(Member).filter_by(phone=b.phone).first(): raise HTTPException(409, "This number is already registered. Please log in.")
    sec.check_otp(b.phone, b.otp)
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
    m = Member(phone=b.phone, name=b.name.strip(), dob=b.dob, gender=b.gender, city=b.city.strip().title(), income_range=b.income_range,
               interests=",".join(b.interests), source_id=src and src.id, first_touch_source_id=(first or src) and (first or src).id, referrer_id=referrer and referrer.id)
    db.add(m); db.flush(); db.add(Referral(referrer_id=m.referrer_id, referred_member_id=m.id)); db.commit()
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
        res, why = evaluate(db, m, s); text = (s.title + " " + s.description).lower()
        out.append({"id": s.id, "title": s.title, "description": s.description, "deadline": s.deadline and s.deadline.isoformat(), "amount": s.amount,
                    "matches_interests": any(i.lower() in text for i in ints), "result": res, "reason": why})
    return sorted(out, key=lambda x: not x["matches_interests"])

@app.get("/api/me/status")
def my_status(t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db); r = db.query(Referral).filter_by(referred_member_id=m.id).first()
    return {"stage": r.stage if r else "Lead", "failure_reason": r.failure_reason if r else None,
            "completions": [{"survey": db.get(Survey, c.survey_id).title, "completed_at": c.completed_at.date().isoformat(), "quality_passed": c.quality_check_passed} for c in db.query(Completion).filter_by(member_id=m.id)],
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

def grid_rows(db, **f):
    stage = {r.referred_member_id: r for r in db.query(Referral)}
    return [{"id": m.id, "referral_id": stage[m.id].id if m.id in stage else None, "name": m.name, "phone": m.phone, "city": m.city, "gender": m.gender,
             "source": m.source.name if m.source else "Unknown", "referrer": m.referrer.name if m.referrer else "",
             "stage": stage[m.id].stage if m.id in stage else "Lead", "created_at": m.created_at.date().isoformat()} for m in member_query(db, **f)]

@app.get("/api/admin/members")
def admin_members(q: str = "", source_id: Optional[int] = None, city: str = "", status: str = "", _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return grid_rows(db, q=q, source_id=source_id, city=city, status=status)

@app.get("/api/admin/members/export")
def export(q: str = "", source_id: Optional[int] = None, city: str = "", status: str = "", _=Depends(admin_auth), db: Session = Depends(db_dep)):
    rows = grid_rows(db, q=q, source_id=source_id, city=city, status=status); buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "name", "phone", "city", "gender", "source", "referrer", "stage", "created_at"], extrasaction="ignore"); w.writeheader(); w.writerows(rows)
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

@app.get("/api/admin/payouts")
def payouts(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": p.id, "member": db.get(Member, p.member_id).name, "kind": "Referral bonus" if p.referral_id else "Survey payment", "amount": p.amount, "status": p.status} for p in db.query(Payout).order_by(Payout.id.desc())]

@app.post("/api/admin/payouts/{pid}/status")
def payout_status(pid: int, status: Literal["Approved", "Paid"], t=Depends(admin_auth), db: Session = Depends(db_dep)):
    p = db.get(Payout, pid)
    if not p: raise HTTPException(404, "Payout not found.")
    if status == "Paid" and p.status != "Approved": raise HTTPException(409, "Ops must approve a payout before it can be marked Paid.")
    p.status = status
    if status == "Approved": p.approved_by, p.approved_at = t["sub"], datetime.utcnow()
    db.commit(); return {"ok": True}

@app.get("/api/admin/source-stats")
def source_stats(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    out = []
    for s in db.query(Source):
        st = [r.stage for r in db.query(Referral).join(Member, Member.id == Referral.referred_member_id).filter(Member.source_id == s.id)]
        out.append({"source": s.name, "type": s.type, "signups": len(st), "fit": sum(x in ("Fit", "Completed") for x in st), "completed": st.count("Completed")})
    return sorted(out, key=lambda x: -x["signups"])

# ---------- messy CSV import ----------
def parse_dob(v):
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d %b %Y"):
        try:
            d = datetime.strptime(v.strip(), f).date()
            if 1920 < d.year <= date.today().year: return d
        except ValueError: pass
    return None

@app.post("/api/admin/import")
async def import_csv(file: UploadFile = File(...), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    try: text = (await file.read()).decode("utf-8-sig", errors="replace")
    except Exception: raise HTTPException(400, "Could not read this file.")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows: raise HTTPException(422, "The file has no data rows.")
    srcs = {s.name.lower(): s for s in db.query(Source)}; seen = {m.phone for m in db.query(Member.phone)}
    added, fixed, skipped, errs = 0, 0, 0, []
    for i, raw in enumerate(rows, start=2):
        try:
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            note = []; phone = norm_phone(r.get("phone") or r.get("mobile"))
            if not phone: raise ValueError("invalid or missing phone")
            if phone in seen: raise ValueError("duplicate phone")
            name = " ".join((r.get("name") or "").split()).title()
            if len(name) < 2: raise ValueError("missing name")
            dob = parse_dob(r.get("dob") or "") if r.get("dob") else None
            if r.get("dob") and not dob: note.append("unreadable DOB cleared")
            g = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}.get((r.get("gender") or "").lower(), "Other" if r.get("gender") else None)
            if r.get("phone") != phone: note.append("phone normalised")
            src = srcs.get((r.get("source") or "").lower())
            m = Member(phone=phone, name=name, dob=dob, gender=g, city=(r.get("city") or "").title() or None, income_range=r.get("income") or r.get("income_range") or None,
                       interests=r.get("interests", "").replace(";", ","), source_id=src and src.id, first_touch_source_id=src and src.id)
            with db.begin_nested(): db.add(m); db.flush(); db.add(Referral(referred_member_id=m.id))
            seen.add(phone); added += 1
            if note: fixed += 1; errs.append({"row": i, "action": "fixed", "reason": ", ".join(note)})
        except Exception as e:
            skipped += 1; errs.append({"row": i, "action": "skipped", "reason": str(e)[:120]})
    db.add(ImportLog(filename=file.filename, total_rows=len(rows), fixed_count=fixed, skipped_count=skipped, error_details_json=json.dumps(errs))); db.commit()
    return {"total_rows": len(rows), "imported": added, "fixed": fixed, "skipped": skipped, "details": errs}

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

# ---------- frontend ----------
@app.get("/")
@app.get("/signup")
def index(): return FileResponse(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html"))
