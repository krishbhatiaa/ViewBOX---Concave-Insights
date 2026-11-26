"""Meta (Instagram/Facebook) lead ads endpoint.

Real lead ads call a webhook with the raw lead, and the app then reads the form
fields from Meta's Graph API. This mock accepts the fields directly, but still
verifies the webhook exactly like production does: with META_WEBHOOK_SECRET set,
every request must carry a valid X-Hub-Signature-256 (HMAC-SHA256 of the raw body)
or an X-Webhook-Token header. Without the secret configured the endpoint stays
open so the README example works out of the box (dev mode, logged as a warning).
"""
import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import db_dep, norm_phone
from ..models import Member, MetaLead, Referral, Source
from ..schemas import MetaLeadIn

log = logging.getLogger("viewbox.meta")
router = APIRouter()


async def verify_webhook(request: Request):
    """Shared-secret check for the Meta webhook (signature or token header).

    Reads the raw body (cached by Starlette) so the HMAC covers exactly the bytes sent.
    """
    raw = await request.body()
    secret = os.getenv("META_WEBHOOK_SECRET", "").strip()
    if not secret:
        log.warning("META_WEBHOOK_SECRET is not set - /api/meta/lead accepts unsigned leads (dev mode)")
        return
    token = request.headers.get("x-webhook-token", "")
    if token and hmac.compare_digest(token, secret):
        return
    sig = request.headers.get("x-hub-signature-256", "")
    if sig.startswith("sha256="):
        digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig[7:], digest):
            return
    raise HTTPException(401, "Invalid or missing Meta webhook signature.")


@router.post("/api/meta/lead")
async def meta_lead(request: Request, b: MetaLeadIn, _=Depends(verify_webhook),
                    db: Session = Depends(db_dep)):
    if db.query(MetaLead).filter_by(lead_id=b.lead_id).first():
        return {"status": "duplicate", "lead_id": b.lead_id}
    f = b.fields
    if isinstance(f, list):
        f = {i.get("name"): (i.get("values") or [""])[0] for i in f if isinstance(i, dict)}
    f = f if isinstance(f, dict) else {}
    name, phone, city = (f.get("name") or f.get("full_name"), norm_phone(f.get("phone") or f.get("phone_number")),
                         f.get("city"))
    lead = MetaLead(lead_id=b.lead_id, form_id=b.form_id, campaign_id=b.campaign_id, ad_id=b.ad_id,
                    raw_payload_json=json.dumps(b.model_dump(), default=str))
    if not phone or not name or len(str(name).strip()) < 2:
        db.add(lead)
        db.commit()  # keep for review, never lose a lead
        raise HTTPException(422, "Lead rejected: a valid name and 10-digit Indian mobile number are required.")
    m = db.query(Member).filter_by(phone=phone).first()
    status = "linked_existing"
    if not m:
        s = db.query(Source).filter_by(unique_slug="meta-ads").first()
        if not s:
            try:
                with db.begin_nested():
                    s = Source(name="Meta Ads", type="meta_ads", unique_slug="meta-ads")
                    db.add(s)
                    db.flush()
            except IntegrityError:
                s = db.query(Source).filter_by(unique_slug="meta-ads").first() or \
                    db.query(Source).filter_by(name="Meta Ads").first()
        m = Member(phone=phone, name=str(name).strip().title(), city=str(city or "").title() or None,
                   source_id=s.id, first_touch_source_id=s.id)
        db.add(m)
        db.flush()
        db.add(Referral(referred_member_id=m.id))
        status = "created"
    lead.member_id = m.id
    db.add(lead)
    db.commit()
    return {"status": status, "member_id": m.id, "source": "Meta Ads", "campaign_id": b.campaign_id}
