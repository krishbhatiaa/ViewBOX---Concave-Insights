"""Meta lead ads webhook: verification, signed delivery, Graph-style envelopes."""
import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import db_dep, norm_phone
from ..models import Member, MetaLead, Referral, Source
from ..schemas import MetaLeadIn
from ..services.meta_graph import flatten_fields, get_fetcher

log = logging.getLogger("viewbox.meta")
router = APIRouter()


async def verify_webhook(request: Request):
    raw = await request.body()
    secret = os.getenv("META_WEBHOOK_SECRET", "").strip()
    if not secret:
        log.warning("META_WEBHOOK_SECRET is not set - /api/meta/lead accepts unsigned leads (dev mode)")
        return
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    sig = request.headers.get("x-hub-signature-256", "")
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(403, "Invalid or missing Meta webhook signature.")


@router.get("/webhooks/meta")
def verify_meta_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    configured = os.getenv("META_VERIFY_TOKEN", "").strip()
    if hub_mode != "subscribe" or not configured:
        raise HTTPException(403, "Invalid Meta webhook verification.")
    if not hmac.compare_digest(hub_verify_token, configured):
        raise HTTPException(403, "Invalid Meta webhook verification.")
    return PlainTextResponse(hub_challenge)


def lead_items(body):
    if not isinstance(body, dict):
        raise HTTPException(422, "Meta webhook body must be a JSON object.")
    if "entry" not in body:
        return [body]
    items = []
    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict) or change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            lead_id = value.get("leadgen_id")
            if not lead_id:
                continue
            items.append({
                "lead_id": lead_id,
                "form_id": value.get("form_id"),
                "campaign_id": value.get("campaign_id"),
                "ad_id": value.get("ad_id") or value.get("adgroup_id"),
                "time": value.get("created_time"),
            })
    if not items:
        raise HTTPException(422, "Meta envelope contained no leadgen entries.")
    return items


def store_lead(item, raw_body, fetcher, db):
    try:
        b = MetaLeadIn.model_validate(item)
    except ValidationError as exc:
        raise HTTPException(422, str(exc))
    if db.query(MetaLead).filter_by(lead_id=b.lead_id).first():
        return {"status": "duplicate", "lead_id": b.lead_id}
    if b.fields is None:
        try:
            b.fields = fetcher.fetch(b.lead_id)
        except Exception:
            raise HTTPException(502, "Could not fetch lead fields from Meta Graph API.")

    f = flatten_fields(b.fields)
    name, phone, city = (f.get("name") or f.get("full_name"),
                         norm_phone(f.get("phone") or f.get("phone_number")),
                         f.get("city"))
    lead = MetaLead(lead_id=b.lead_id, form_id=b.form_id, campaign_id=b.campaign_id, ad_id=b.ad_id,
                    raw_payload_json=json.dumps(raw_body, default=str))
    if not phone or not name or len(str(name).strip()) < 2:
        db.add(lead)
        db.commit()
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


@router.post("/api/meta/lead")
async def meta_lead(request: Request, _=Depends(verify_webhook), db: Session = Depends(db_dep)):
    raw = await request.body()
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(422, "Invalid JSON body.")
    items = lead_items(body)
    fetcher = get_fetcher()
    results = [store_lead(item, body, fetcher, db) for item in items]
    return results[0] if len(results) == 1 else {"status": "processed", "leads": results}
