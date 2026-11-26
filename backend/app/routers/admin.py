"""Admin panel: login, sources, surveys, respondent grid + export, referral stages,
payout ledger, source dashboard, fraud queue and manual eligibility overrides."""
import json
import logging
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from .. import fraud
from .. import security as sec
from ..deps import admin_auth, db_dep, link_for, slugify
from ..models import (AdminOverride, AdminUser, AuditEvent, Completion, FraudFlag, Member, MetaLead,
                       Payout, Referral, Source, Survey, SurveyRule, TouchEvent)
from ..schemas import (AdminLogin, FlagReviewIn, GridFilterIn, OverrideIn, PayoutStatusIn, SourceIn,
                        StageIn, SuggestRulesIn, SurveyIn, SurveyPatchIn, validate_survey_deadline)
from ..services import audit, grid as grid_svc, sheets
from ..services.referral import set_stage as apply_stage
from ..services.rule_suggest import suggest_rules

log = logging.getLogger("viewbox.admin")
router = APIRouter()


def survey_interests(survey: Survey) -> List[str]:
    return [tag for tag in (survey.interests or "").split(",") if tag]


@router.post("/api/admin/login")
def admin_login(b: AdminLogin, db: Session = Depends(db_dep)):
    a = db.query(AdminUser).filter_by(email=b.email.lower()).first()
    if not a or not sec.check_pw(b.password, a.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return {"token": sec.make_token(a.email, "admin")}


# ---------- append-only audit trail ----------
@router.get("/api/admin/audit")
def list_audit(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
               _=Depends(admin_auth), db: Session = Depends(db_dep)):
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).offset(offset).limit(limit).all()
    return [{"id": e.id, "actor_id": e.actor_id, "actor_role": e.actor_role, "action": e.action,
             "resource_type": e.resource_type, "resource_id": e.resource_id,
             "details": json.loads(e.details_json) if e.details_json else None,
             "ip": e.ip, "created_at": e.created_at.isoformat()} for e in rows]


@router.get("/api/admin/touches")
def list_touches(member_id: Optional[int] = None, limit: int = Query(100, ge=1, le=500),
                 _=Depends(admin_auth), db: Session = Depends(db_dep)):
    q = db.query(TouchEvent)
    if member_id:
        q = q.filter_by(member_id=member_id)
    return [{"id": t.id, "source_slug": t.source_slug, "ref_slug": t.ref_slug, "ip": t.ip,
             "user_agent": t.user_agent, "member_id": t.member_id, "created_at": t.created_at.isoformat()}
            for t in q.order_by(TouchEvent.id.desc()).limit(limit)]


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
             "quota": x.quota, "amount": x.amount, "interests": survey_interests(x),
             "completions": db.query(Completion).filter_by(survey_id=x.id).count(),
             "rules": [{"rule_type": r.rule_type, "value": r.value, "strict_or_flexible": r.strict_or_flexible}
                       for r in x.rules]} for x in db.query(Survey).order_by(Survey.id.desc())]


@router.post("/api/admin/surveys", status_code=201)
def add_survey(b: SurveyIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    data = b.model_dump(exclude={"rules"})
    data["interests"] = ",".join(data["interests"])
    s = Survey(**data,
               rules=[SurveyRule(**r.model_dump(), operator="between" if r.rule_type == "age" else "in")
                      for r in b.rules])
    db.add(s)
    db.commit()
    return {"id": s.id}


@router.patch("/api/admin/surveys/{sid}")
def patch_survey(sid: int, b: SurveyPatchIn, _=Depends(admin_auth), db: Session = Depends(db_dep)):
    s = db.get(Survey, sid)
    if not s:
        raise HTTPException(404, "Survey not found.")
    changes = b.model_dump(exclude_unset=True)
    if "deadline" in changes:
        try:
            validate_survey_deadline(changes["deadline"], s.created_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    for field, value in changes.items():
        if field == "interests":
            value = ",".join(value)
        setattr(s, field, value)
    db.commit()
    return {"id": s.id, "title": s.title, "status": s.status,
            "deadline": s.deadline and s.deadline.date().isoformat(), "quota": s.quota, "amount": s.amount,
            "interests": survey_interests(s),
            "completions": db.query(Completion).filter_by(survey_id=s.id).count(),
            "rules": [{"rule_type": r.rule_type, "value": r.value, "strict_or_flexible": r.strict_or_flexible}
                      for r in s.rules]}


@router.post("/api/admin/suggest-rules")
def suggest_survey_rules(b: SuggestRulesIn, _=Depends(admin_auth)):
    """Suggest eligibility rules for a survey title/description.

    Returns candidates only — nothing is saved. The admin edits them in the
    create-survey form and saves through POST /api/admin/surveys as usual.
    """
    return suggest_rules(b.title, b.description)


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


# ---------- Google Sheets sync ----------
@router.get("/api/admin/sheets/status")
def sheets_status(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    return sheets.status(db)


@router.post("/api/admin/sheets/push")
def sheets_push(b: Optional[GridFilterIn] = Body(None), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    try:
        return sheets.push(db, (b or GridFilterIn()).model_dump())
    except sheets.SheetSyncError as exc:
        raise HTTPException(502, str(exc))


@router.post("/api/admin/sheets/pull")
def sheets_pull(worksheet: str = Query("sheet1", max_length=100), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    try:
        return sheets.pull(db, worksheet)
    except sheets.SheetSyncError as exc:
        raise HTTPException(502, str(exc))


# ---------- referral stages ----------
@router.get("/api/admin/referrals")
def list_referrals(stage: Optional[Literal["Lead", "Fit", "Completed", "Failed"]] = None,
                   q: str = Query("", max_length=100), limit: int = Query(100, ge=1, le=500),
                   offset: int = Query(0, ge=0), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    referrer = aliased(Member)
    rows = db.query(Referral).join(Member, Member.id == Referral.referred_member_id) \
             .outerjoin(referrer, Referral.referrer_id == referrer.id)
    if stage:
        rows = rows.filter(Referral.stage == stage)
    if q:
        pattern = f"%{q}%"
        rows = rows.filter(or_(Member.name.like(pattern), referrer.name.like(pattern),
                               Member.city.like(pattern), Referral.failure_reason.like(pattern)))
    out = []
    for r in rows.order_by(Referral.updated_at.desc(), Referral.id.desc()).offset(offset).limit(limit):
        member = db.get(Member, r.referred_member_id)
        referrer_member = db.get(Member, r.referrer_id) if r.referrer_id else None
        source = db.get(Source, member.source_id) if member and member.source_id else None
        out.append({"id": r.id, "referrer_id": r.referrer_id,
                    "referrer": referrer_member.name if referrer_member else None,
                    "member_id": r.referred_member_id, "member": member.name if member else None,
                    "city": member.city if member else None, "source": source.name if source else None,
                    "stage": r.stage, "failure_reason": r.failure_reason,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None})
    return out


@router.post("/api/admin/referrals/{rid}/stage")
def set_stage(request: Request, rid: int, b: StageIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    ip = request.client.host if request.client else None
    return apply_stage(db, rid, b.stage, b.failure_reason, b.survey_id, b.quality_check_passed,
                       actor=t, ip=ip)


# ---------- payout ledger ----------
@router.get("/api/admin/payouts")
def payouts(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    out = []
    for p in db.query(Payout).order_by(Payout.id.desc()):
        m = db.get(Member, p.member_id)
        if m is None:
            raise HTTPException(404, "Member not found.")
        out.append({"id": p.id, "member": m.name,
                    "kind": "Referral bonus" if p.referral_id else "Survey payment",
                    "amount": p.amount, "status": p.status})
    return out


@router.post("/api/admin/payouts/batch-approve")
def batch_approve_payouts(request: Request, b: dict = Body(...), t=Depends(admin_auth),
                          db: Session = Depends(db_dep)):
    ids = b.get("ids")
    if not isinstance(ids, list):
        raise HTTPException(422, "Please provide a list of payout ids.")
    ip = request.client.host if request.client else None
    actor_id, role = audit.identity(t)
    results = []
    try:
        for pid in ids:
            if not isinstance(pid, int):
                results.append({"id": pid, "ok": False, "error": "Invalid payout id."})
                continue
            with db.begin_nested():
                p = db.get(Payout, pid)
                if not p:
                    results.append({"id": pid, "ok": False, "error": "Payout not found."})
                    continue
                if p.status == "Paid":
                    results.append({"id": pid, "ok": False, "error": "Paid payouts cannot be re-approved."})
                    continue
                changed = p.status != "Approved"
                p.status, p.approved_by, p.approved_at = "Approved", t["sub"], datetime.utcnow()
                if changed:
                    audit.log(actor_id, role, "payout_status_changed", "payout", pid, {"status": "Approved"}, ip, db=db)
                results.append({"id": pid, "ok": True, "status": p.status, "changed": changed})
        db.commit()
    except Exception as exc:
        db.rollback()
        log.error("batch payout approval failed: %s", type(exc).__name__)
        raise HTTPException(500, "Could not approve payouts. Please try again.") from exc
    return {"results": results, "approved": sum(r["ok"] for r in results),
            "failed": sum(not r["ok"] for r in results)}


@router.post("/api/admin/payouts/{pid}/status")
def payout_status(request: Request, pid: int, b: Optional[PayoutStatusIn] = Body(None),
                  status: Optional[Literal["Approved", "Paid"]] = Query(None),
                  t=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Accepts the status as JSON body (frontend) or query string (README examples)."""
    val = (b and b.status) or status
    if not val:
        raise HTTPException(422, "Please give a status of Approved or Paid.")
    try:
        p = db.get(Payout, pid)
        if not p:
            raise HTTPException(404, "Payout not found.")
        if val == "Paid" and p.status != "Approved":
            raise HTTPException(409, "Ops must approve a payout before it can be marked Paid.")
        p.status = val
        if val == "Approved":
            p.approved_by, p.approved_at = t["sub"], datetime.utcnow()
        actor_id, role = audit.identity(t)
        audit.log(actor_id, role, "payout_status_changed", "payout", pid, {"status": val},
                  request.client.host if request.client else None, db=db)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        log.error("payout status change failed: %s", type(exc).__name__)
        raise HTTPException(500, "Could not update this payout. Please try again.") from exc
    return {"ok": True}


# ---------- source dashboard ----------
@router.get("/api/admin/source-stats")
def source_stats(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    out = []
    for s in db.query(Source):
        refs = db.query(Referral).join(Member, Member.id == Referral.referred_member_id) \
                 .filter(Member.source_id == s.id).all()
        st = [r.stage for r in refs]
        channels: dict[str, int] = {}
        for r in refs:
            key = r.channel or "direct"
            channels[key] = channels.get(key, 0) + 1
        out.append({"source": s.name, "type": s.type, "signups": len(st),
                    "fit": sum(x in ("Fit", "Completed") for x in st), "completed": st.count("Completed"),
                    "completion_rate": st.count("Completed") / max(len(st), 1),
                    "by_channel": [{"channel": k, "count": v} for k, v in
                                   sorted(channels.items(), key=lambda kv: -kv[1])]})
    return sorted(out, key=lambda x: -x["signups"])


# ---------- Meta leads (view + per-campaign breakdown) ----------
@router.get("/api/admin/meta-leads")
def meta_leads(limit: int = Query(100, ge=1, le=500), _=Depends(admin_auth), db: Session = Depends(db_dep)):
    rows = db.query(MetaLead).order_by(MetaLead.id.desc()).limit(limit).all()
    out = []
    for x in rows:
        member_name = None
        if x.member_id:
            m = db.get(Member, x.member_id)
            if m is None:
                raise HTTPException(404, "Member not found.")
            member_name = m.name
        out.append({"id": x.id, "lead_id": x.lead_id, "campaign_id": x.campaign_id, "ad_id": x.ad_id,
                    "form_id": x.form_id, "received_at": x.received_at.isoformat(),
                    "member_id": x.member_id, "member": member_name,
                    "status": "linked" if x.member_id else "needs review"})
    return out


@router.get("/api/admin/meta-leads/stats")
def meta_lead_stats(_=Depends(admin_auth), db: Session = Depends(db_dep)):
    """Per-campaign (and per-ad) counts of leads, linked members and leads needing review."""
    def bucket(rows):
        linked = sum(1 for r in rows if r.member_id)
        return {"leads": len(rows), "linked": linked, "needs_review": len(rows) - linked}

    by_campaign: dict[str, list] = {}
    by_ad: dict[str, list] = {}
    for x in db.query(MetaLead).all():
        by_campaign.setdefault(x.campaign_id or "(no campaign)", []).append(x)
        by_ad.setdefault(x.ad_id or "(no ad)", []).append(x)
    return {
        "total": bucket(db.query(MetaLead).all()),
        "by_campaign": [{"campaign_id": k, **bucket(v)} for k, v in
                        sorted(by_campaign.items(), key=lambda kv: -len(kv[1]))],
        "by_ad": [{"ad_id": k, **bucket(v)} for k, v in sorted(by_ad.items(), key=lambda kv: -len(kv[1]))],
    }


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
def review_flag(request: Request, fid: int, b: FlagReviewIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
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
    actor_id, role = audit.identity(t)
    audit.log(actor_id, role, "fraud_flag_reviewed", "fraud_flag", fid,
              {"status": f.status, "note": b.note},
              request.client.host if request.client else None, db=db)
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
    out = []
    for o in q.order_by(AdminOverride.id.desc()):
        m = db.get(Member, o.member_id)
        if m is None:
            raise HTTPException(404, "Member not found.")
        s = db.get(Survey, o.survey_id)
        if s is None:
            raise HTTPException(404, "Survey not found.")
        out.append({"id": o.id, "member_id": o.member_id, "member": m.name,
                    "survey_id": o.survey_id, "survey": s.title,
                    "reason": o.reason, "created_at": o.created_at.date().isoformat()})
    return out


@router.post("/api/admin/overrides", status_code=201)
def create_override(b: OverrideIn, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    if not db.get(Member, b.member_id):
        raise HTTPException(404, "Member not found.")
    if not db.get(Survey, b.survey_id):
        raise HTTPException(404, "Survey not found.")
    if db.query(AdminOverride).filter_by(member_id=b.member_id, survey_id=b.survey_id).first():
        raise HTTPException(409, "An override already exists for this member and survey.")
    o = AdminOverride(member_id=b.member_id, survey_id=b.survey_id, overridden_by=t["sub"],
                      reason=b.reason.strip())
    db.add(o)
    try:
        db.flush()
        actor_id, role = audit.identity(t)
        audit.log(actor_id, role, "override_created", "override", o.id,
                  {"member_id": b.member_id, "survey_id": b.survey_id}, db=db)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An override already exists for this member and survey.")
    return {"ok": True}


@router.delete("/api/admin/overrides/{oid}")
def delete_override(oid: int, t=Depends(admin_auth), db: Session = Depends(db_dep)):
    o = db.get(AdminOverride, oid)
    if not o:
        raise HTTPException(404, "Override not found.")
    actor_id, role = audit.identity(t)
    audit.log(actor_id, role, "override_deleted", "override", oid,
              {"member_id": o.member_id, "survey_id": o.survey_id}, db=db)
    db.delete(o)
    db.commit()
    return {"ok": True}
