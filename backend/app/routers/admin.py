"""Admin panel: login, sources, surveys, respondent grid + export, referral stages,
payout ledger, source dashboard, fraud queue and manual eligibility overrides."""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import fraud
from .. import security as sec
from ..deps import admin_auth, db_dep, link_for, slugify
from ..models import (AdminOverride, AdminUser, Completion, FraudFlag, Member, Payout, Referral,
                      Source, Survey, SurveyRule)
from ..schemas import AdminLogin, FlagReviewIn, OverrideIn, PayoutStatusIn, SourceIn, StageIn, SurveyIn
from ..services import grid as grid_svc
from ..services.referral import set_stage as apply_stage

router = APIRouter()


@router.post("/api/admin/login")
def admin_login(b: AdminLogin, db: Session = Depends(db_dep)):
    a = db.query(AdminUser).filter_by(email=b.email.lower()).first()
    if not a or not sec.check_pw(b.password, a.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return {"token": sec.make_token(a.email, "admin")}


# ---------- sources (data, not hardcoded) ----------
@router.get("/api/admin/sources")
def list_sources(request: Request, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": s.id, "name": s.name, "type": s.type, "link": link_for(s, request)}
            for s in db.query(Source).order_by(Source.name)]


@router.post("/api/admin/sources", status_code=201)
def add_source(b: SourceIn, request: Request, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    if db.query(Source).filter_by(name=b.name).first():
        raise HTTPException(409, "A source with this name already exists.")
    base = slugify(b.name) or "source"
    slug, n = base, 2
    while db.query(Source).filter_by(unique_slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    s = Source(name=b.name, type=slugify(b.type) or "other", unique_slug=slug)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name, "type": s.type, "link": link_for(s, request)}


# ---------- surveys + rules ----------
@router.get("/api/admin/surveys")
def admin_surveys(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": x.id, "title": x.title, "status": x.status, "deadline": x.deadline and x.deadline.date().isoformat(),
             "quota": x.quota, "amount": x.amount,
             "completions": db.query(Completion).filter_by(survey_id=x.id).count(),
             "rules": [{"rule_type": r.rule_type, "value": r.value, "strict_or_flexible": r.strict_or_flexible}
                       for r in x.rules]} for x in db.query(Survey).order_by(Survey.id.desc())]


@router.post("/api/admin/surveys", status_code=201)
def add_survey(b: SurveyIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    s = Survey(**b.model_dump(exclude={"rules"}),
               rules=[SurveyRule(**r.model_dump(), operator="between" if r.rule_type == "age" else "in")
                      for r in b.rules])
    db.add(s)
    db.commit()
    return {"id": s.id}


# ---------- respondent grid + export ----------
@router.get("/api/admin/members")
def admin_members(q: str = Query("", max_length=100), source_id: Optional[int] = None,
                  city: str = Query("", max_length=60), status: str = Query("", max_length=30),
                  survey_id: Optional[int] = None, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return grid_svc.grid_rows(db, q=q, source_id=source_id, city=city, status=status, survey_id=survey_id)


@router.get("/api/admin/members/export")
def export(q: str = Query("", max_length=100), source_id: Optional[int] = None,
           city: str = Query("", max_length=60), status: str = Query("", max_length=30),
           survey_id: Optional[int] = None, format: str = Query("csv", pattern="^(csv|xlsx)$"),
           _=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Download the current grid view as CSV or Excel (.xlsx)."""
    rows = grid_svc.grid_rows(db, q=q, source_id=source_id, city=city, status=status, survey_id=survey_id)
    rows = grid_svc.flatten(rows)
    fields = grid_svc.export_fields(survey_id)
    if format == "xlsx":
        return StreamingResponse(grid_svc.to_xlsx(rows, fields),
                                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=members.xlsx"})
    return StreamingResponse(iter([grid_svc.to_csv(rows, fields)]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=members.csv"})


# ---------- referral stages ----------
@router.post("/api/admin/referrals/{rid}/stage")
def set_stage(rid: int, b: StageIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    return apply_stage(db, rid, b.stage, b.failure_reason, b.survey_id, b.quality_check_passed)


# ---------- payout ledger ----------
@router.get("/api/admin/payouts")
def payouts(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return [{"id": p.id, "member": db.get(Member, p.member_id).name,
             "kind": "Referral bonus" if p.referral_id else "Survey payment", "amount": p.amount, "status": p.status}
            for p in db.query(Payout).order_by(Payout.id.desc())]


@router.post("/api/admin/payouts/{pid}/status")
def payout_status(pid: int, b: Optional[PayoutStatusIn] = Body(None),
                  status: Optional[Literal["Approved", "Paid"]] = Query(None),
                  t=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Accepts the status as JSON body (frontend) or query string (README examples)."""
    val = (b and b.status) or status
    if not val:
        raise HTTPException(422, "Please give a status of Approved or Paid.")
    p = db.get(Payout, pid)
    if not p:
        raise HTTPException(404, "Payout not found.")
    if val == "Paid" and p.status != "Approved":
        raise HTTPException(409, "Ops must approve a payout before it can be marked Paid.")
    p.status = val
    if val == "Approved":
        p.approved_by, p.approved_at = t["sub"], datetime.utcnow()
    db.commit()
    return {"ok": True}


# ---------- source dashboard ----------
@router.get("/api/admin/source-stats")
def source_stats(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    out = []
    for s in db.query(Source):
        st = [r.stage for r in db.query(Referral).join(Member, Member.id == Referral.referred_member_id)
              .filter(Member.source_id == s.id)]
        out.append({"source": s.name, "type": s.type, "signups": len(st),
                    "fit": sum(x in ("Fit", "Completed") for x in st), "completed": st.count("Completed")})
    return sorted(out, key=lambda x: -x["signups"])


# ---------- fraud review queue ----------
@router.get("/api/admin/fraud-flags")
def fraud_flags(status: Literal["open", "Cleared", "Confirmed", "all"] = "open",
                _=Depends(admin_auth), db: Session = Depends(db_dep)):
    q = db.query(FraudFlag)
    if status != "all":
        q = q.filter_by(status=status)
    out = []
    for f in q.order_by(FraudFlag.id.desc()):
        m = db.get(Member, f.member_id)
        out.append({"id": f.id, "member_id": f.member_id, "name": m.name if m else "(deleted member)",
                    "phone": m.phone if m else "", "flag_type": f.flag_type, "details": f.details,
                    "status": f.status, "created_at": f.created_at.date().isoformat(),
                    "reviewed_by": f.reviewed_by})
    return out


@router.post("/api/admin/fraud-flags/{fid}/review")
def review_flag(fid: int, b: FlagReviewIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    f = db.get(FraudFlag, fid)
    if not f:
        raise HTTPException(404, "Flag not found.")
    f.status = b.status  # Cleared or Confirmed — rows are never deleted
    if b.note:
        f.details = f"{f.details} · Review note: {b.note}"
    f.reviewed_by, f.reviewed_at = t["sub"], datetime.utcnow()
    db.flush()  # autoflush is off; flush so the open-count below sees the new status
    open_left = db.query(FraudFlag).filter_by(member_id=f.member_id, status="open").count()
    m = db.get(Member, f.member_id)
    if m:
        m.is_flagged = open_left > 0
    db.commit()
    return {"ok": True, "status": f.status, "member_flagged": bool(m and m.is_flagged)}


@router.post("/api/admin/fraud/scan")
def fraud_scan(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Re-check everyone for device/IP bursts and referral rings."""
    return {"flags_created": fraud.scan(db)}


# ---------- manual eligibility override ----------
@router.get("/api/admin/overrides")
def list_overrides(member_id: Optional[int] = None, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    q = db.query(AdminOverride)
    if member_id:
        q = q.filter_by(member_id=member_id)
    return [{"id": o.id, "member_id": o.member_id, "member": db.get(Member, o.member_id).name,
             "survey_id": o.survey_id, "survey": db.get(Survey, o.survey_id).title,
             "reason": o.reason, "created_at": o.created_at.date().isoformat()}
            for o in q.order_by(AdminOverride.id.desc())]


@router.post("/api/admin/overrides", status_code=201)
def create_override(b: OverrideIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    if not db.get(Member, b.member_id):
        raise HTTPException(404, "Member not found.")
    if not db.get(Survey, b.survey_id):
        raise HTTPException(404, "Survey not found.")
    if db.query(AdminOverride).filter_by(member_id=b.member_id, survey_id=b.survey_id).first():
        raise HTTPException(409, "An override already exists for this member and survey.")
    db.add(AdminOverride(member_id=b.member_id, survey_id=b.survey_id, overridden_by=t["sub"],
                         reason=b.reason.strip()))
    db.commit()
    return {"ok": True}


@router.delete("/api/admin/overrides/{oid}")
def delete_override(oid: int, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    o = db.get(AdminOverride, oid)
    if not o:
        raise HTTPException(404, "Override not found.")
    db.delete(o)
    db.commit()
    return {"ok": True}
