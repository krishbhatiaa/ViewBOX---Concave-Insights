"""Member portal: profile, live surveys with eligibility, own status, my referrals."""
import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import security as sec
from ..deps import base_url, db_dep, me, member_auth
from ..eligibility import evaluate, next_eligible_date, record_result
from ..models import Completion, Payout, Referral, Survey
from ..schemas import MeOut, ReferralOut, StatusOut, SurveyOut

router = APIRouter()


def referral_link(request: Request, member_id: int, channel: str) -> str:
    return f"{base_url(request)}/signup?ref={sec.sign_link('ref', str(member_id))}&ch={quote(channel)}"


@router.get("/api/me", response_model=MeOut)
def get_me(request: Request, ch: str = Query("direct", max_length=30),
           t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db)
    d = next_eligible_date(db, m)
    return {"id": m.id, "name": m.name, "phone": m.phone, "city": m.city,
            "interests": [i for i in (m.interests or "").split(",") if i],
            "next_eligible_date": d and d.isoformat(),
            "referral_link": referral_link(request, m.id, ch)}


@router.get("/api/me/referral-qr")
def referral_qr(request: Request, ch: str = Query("direct", max_length=30),
                t=Depends(member_auth), db: Session = Depends(db_dep)):
    m = me(t, db)
    import qrcode

    image = qrcode.make(referral_link(request, m.id, ch))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": 'attachment; filename="referral-qr.png"'})


@router.get("/api/surveys", response_model=list[SurveyOut])
def surveys(t=Depends(member_auth), db: Session = Depends(db_dep)):
    """Live surveys for this member; every computed result is saved to eligibility_results."""
    m = me(t, db)
    ints = [i for i in (m.interests or "").split(",") if i]
    out = []
    for s in db.query(Survey).filter_by(status="live"):
        res, why = evaluate(db, m, s)
        record_result(db, m.id, s.id, res, why)
        text = (s.title + " " + s.description).lower()
        out.append({"id": s.id, "title": s.title, "description": s.description,
                    "deadline": s.deadline and s.deadline.isoformat(), "amount": s.amount,
                    "matches_interests": any(i.lower() in text for i in ints), "result": res, "reason": why})
    db.commit()
    return sorted(out, key=lambda x: not x["matches_interests"])


@router.get("/api/me/status", response_model=StatusOut)
def my_status(t=Depends(member_auth), db: Session = Depends(db_dep)):
    """Member's own pipeline stage, completions and earnings - so they never need to call ops."""
    m = me(t, db)
    r = db.query(Referral).filter_by(referred_member_id=m.id).first()
    comps = []
    for c in db.query(Completion).filter_by(member_id=m.id):
        sv = db.get(Survey, c.survey_id) if c.survey_id else None
        comps.append({"survey": sv.title if sv else "Completed before joining (imported)",
                      "completed_at": c.completed_at.date().isoformat(), "quality_passed": c.quality_check_passed})
    return {"stage": r.stage if r else "Lead", "failure_reason": r.failure_reason if r else None,
            "completions": comps,
            "payouts": [{"kind": "Referral bonus" if p.referral_id else "Survey payment", "amount": p.amount,
                         "status": p.status} for p in db.query(Payout).filter_by(member_id=m.id)]}


@router.get("/api/me/referrals", response_model=list[ReferralOut])
def my_referrals(t=Depends(member_auth), db: Session = Depends(db_dep)):
    """Each referred friend's stage + failure reason, phone masked (98XXXXXX21)."""
    rows = db.query(Referral).filter_by(referrer_id=t["sub"]).all()
    bonus = {p.referral_id: p for p in db.query(Payout).filter(Payout.member_id == t["sub"], Payout.referral_id != None)}
    return [{"bonus": {"amount": bonus[r.id].amount, "status": bonus[r.id].status} if r.id in bonus else None,
              "friend": r.referred.name, "phone": r.referred.phone, "stage": r.stage,
             "failure_reason": r.failure_reason, "updated_at": r.updated_at.isoformat()} for r in rows]
