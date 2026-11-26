"""Referral pipeline: Lead -> Fit -> Completed/Failed, completions, payouts, cool-off."""
import logging
import os
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Completion, Payout, Referral, Survey
from . import audit

log = logging.getLogger("viewbox.referral")
BONUS = Decimal(os.getenv("REFERRAL_BONUS", "100"))


def set_stage(db: Session, rid: int, stage: str, failure_reason: str | None,
              survey_id: int | None, quality_check_passed: bool,
              actor=None, ip: str | None = None) -> dict:
    """Move one referral row to the next stage (ops action).

    Completed writes the completion (starts the 3-month cool-off when the quality
    check passed), creates the survey payment and the referrer's bonus payout.
    Failed requires a reason that the referrer can see. Completed is irreversible.
    """
    try:
        r = db.get(Referral, rid)
        if not r:
            raise HTTPException(404, "Referral not found.")
        if r.stage == "Completed" and stage != "Completed":
            raise HTTPException(409, "This member already completed a survey, so the stage can't be changed.")
        reason = failure_reason
        if stage == "Failed" and not reason:
            raise HTTPException(422, "Please give a reason when marking Failed.")
        if stage == "Completed":
            sv = db.get(Survey, survey_id) if survey_id else None
            if not sv:
                raise HTTPException(422, "Please choose which survey was completed.")
            if db.query(Completion).filter_by(member_id=r.referred_member_id, survey_id=sv.id).first():
                raise HTTPException(409, "This completion is already recorded.")
            db.add(Completion(member_id=r.referred_member_id, survey_id=sv.id,
                              quality_check_passed=quality_check_passed))  # starts cool-off when quality passed
            if quality_check_passed:
                db.add(Payout(member_id=r.referred_member_id, survey_id=sv.id, amount=sv.amount))
                if r.referrer_id and not db.query(Payout).filter_by(referral_id=r.id).first():
                    db.add(Payout(member_id=r.referrer_id, survey_id=sv.id, referral_id=r.id, amount=BONUS))
            else:
                stage, reason = "Failed", "Did not pass the quality check, so no payment is due."
        r.stage, r.failure_reason, r.updated_at = stage, reason if stage == "Failed" else None, datetime.utcnow()
        actor_id, role = audit.identity(actor)
        audit.log(actor_id, role, "referral_stage_changed", "referral", rid, {"stage": r.stage}, ip, db=db)
        db.commit()
        return {"ok": True, "stage": r.stage}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        log.error("referral stage change failed: %s", type(exc).__name__)
        raise HTTPException(500, "Could not update this referral. Please try again.") from exc
