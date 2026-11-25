"""Public auth: mock OTP login, signup with signed source/referral links, link resolution."""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import fraud
from .. import security as sec
from ..deps import client_ip, db_dep, norm_phone
from ..models import Member, Referral, Source
from ..schemas import LoginIn, PhoneIn, SignupIn

router = APIRouter()


@router.post("/api/otp/request")
def otp_request(b: PhoneIn, request: Request, db: Session = Depends(db_dep)):
    """Mock OTP: returned in the response and shown on screen. No SMS."""
    sec.enforce_ip_limit(request, "otp")  # slow down scripted OTP floods per network
    return {"otp": sec.issue_otp(b.phone), "is_member": bool(db.query(Member).filter_by(phone=b.phone).first())}


@router.post("/api/login")
def login(b: LoginIn, db: Session = Depends(db_dep)):
    m = db.query(Member).filter_by(phone=b.phone).first()
    if not m:
        raise HTTPException(404, "No account for this number yet. Please sign up.")
    sec.check_otp(b.phone, b.otp)
    return {"token": sec.make_token(m.id, "member")}


@router.post("/api/signup")
def signup(b: SignupIn, request: Request, x_device_id: str = Header(None), db: Session = Depends(db_dep)):
    sec.check_otp(b.phone, b.otp)  # verify first so unauthenticated callers can't spam flags
    sec.enforce_ip_limit(request, "signup")
    existing = db.query(Member).filter_by(phone=b.phone).first()
    if existing:
        fraud.add_flag(db, existing.id, "duplicate_signup",
                       f"Another sign-up attempt with this phone at {datetime.utcnow():%Y-%m-%d %H:%M} UTC.")
        db.commit()
        raise HTTPException(409, "This number is already registered. Please log in.")
    src = referrer = None
    notes = []
    if b.src:
        slug = sec.verify_link("src", b.src)
        src = db.query(Source).filter_by(unique_slug=slug).first() if slug else None
        if not src:
            notes.append("Source link could not be verified and was ignored.")
    if b.ref:
        rid = sec.verify_link("ref", b.ref)
        referrer = db.get(Member, int(rid)) if rid and rid.isdigit() else None
        if not referrer:
            notes.append("Referral link could not be verified and was ignored.")
    if not referrer and b.referrer_phone:  # typed referrer: matched by exact phone, never by ambiguous name
        referrer = db.query(Member).filter_by(phone=norm_phone(b.referrer_phone) or "-").first()
        if not referrer or referrer.phone == b.phone:
            referrer = None
            notes.append("We couldn't find a member with that referrer number.")
    first = None
    fslug = sec.verify_link("src", b.first_src) if b.first_src else None
    if fslug:
        first = db.query(Source).filter_by(unique_slug=fslug).first()
    if not src and referrer:
        src = db.query(Source).filter_by(type="referral").first()  # ref only -> source=Referral
    if not src and b.how_heard_source_id:
        src = db.get(Source, b.how_heard_source_id)
    m = Member(phone=b.phone, name=b.name.strip(), dob=b.dob, gender=b.gender, city=b.city.strip().title(),
               income_range=b.income_range, interests=",".join(b.interests), source_id=src and src.id,
               first_touch_source_id=(first or src) and (first or src).id,
               referrer_id=referrer and referrer.id, ip=client_ip(request), device_id=x_device_id)
    db.add(m)
    db.flush()
    db.add(Referral(referrer_id=m.referrer_id, referred_member_id=m.id))
    fraud.on_signup(db, m, referrer, m.ip, m.device_id)
    db.commit()
    return {"token": sec.make_token(m.id, "member"), "notes": notes}


@router.get("/api/links/resolve")
def resolve_links(src: str = Query("", max_length=400), ref: str = Query("", max_length=400),
                  db: Session = Depends(db_dep)):
    """Lets the signup page greet the visitor and decide whether to show 'How did you hear about us?'."""
    slug = sec.verify_link("src", src) if src else None
    s = db.query(Source).filter_by(unique_slug=slug).first() if slug else None
    rid = sec.verify_link("ref", ref) if ref else None
    r = db.get(Member, int(rid)) if rid and rid.isdigit() else None
    return {"source": s and s.name, "referrer": r and r.name.split()[0], "needs_fallback": not s and not r}


@router.get("/api/sources/public")
def public_sources(db: Session = Depends(db_dep)):
    return [{"id": s.id, "name": s.name} for s in db.query(Source).order_by(Source.name)]
