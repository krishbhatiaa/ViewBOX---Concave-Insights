"""Google Forms integration: form creation, response capture and .xlsx sync."""
import csv
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..models import GoogleFormLead, Member, Referral, Source, Survey
from . import sheets

log = logging.getLogger("viewbox.google_forms")
GOOGLE_FORM_SOURCE = "Google Form"
XLSX_FIELDS = ["id", "response_id", "form_id", "survey", "name", "phone", "city", "email",
               "status", "source", "received_at"]
FORM_SCOPES = ["https://www.googleapis.com/auth/forms.body",
               "https://www.googleapis.com/auth/drive.file"]


class FormsError(Exception):
    """Human-readable Google Forms failure surfaced by the routers."""


class FormsNotConfigured(FormsError):
    """Google credentials or a responses Sheet ID are missing."""


def _flatten_fields(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        out = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            key = item.get("name") or item.get("key") or item.get("label")
            item_value = item.get("values") or item.get("value") or ""
            if isinstance(item_value, list):
                item_value = item_value[0] if item_value else ""
            if key:
                out[str(key)] = item_value
        return out
    raise FormsError("Form answers must be an object or a list of question answers.")


def _pick(fields: Dict[str, Any], *names: str) -> Any:
    lowered = {str(k).strip().lower(): v for k, v in fields.items()}
    for name in names:
        value = lowered.get(name.strip().lower())
        if value not in (None, ""):
            return value
    return None


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise FormsError("Please give a valid 10-digit Indian phone number.")
    return digits


def _questions(survey: Survey) -> List[tuple[str, bool]]:
    rules = {r.rule_type for r in survey.rules}
    questions = [("Full name", True), ("Phone number (10 digits)", True)]
    if "age" in rules:
        questions.append(("Age (years)", True))
    if "city" in rules:
        questions.append(("City", True))
    if "gender" in rules:
        questions.append(("Gender", False))
    if "income" in rules:
        questions.append(("Income range", False))
    questions.extend([("Interests (comma separated)", False),
                      ("Anything else you would like us to know?", False)])
    return questions


def _share_form(client: Any, headers: dict, form_id: str) -> None:
    emails = [x.strip() for x in os.getenv("GOOGLE_FORM_SHARE_WITH", "").split(",") if x.strip()]
    for email in emails:
        try:
            response = client.post(
                f"https://www.googleapis.com/drive/v3/files/{form_id}/permissions",
                headers=headers,
                params={"sendNotificationEmail": "false"},
                json={"type": "user", "role": "reader", "emailAddress": email},
            )
            response.raise_for_status()
        except Exception as exc:
            log.warning("created form %s but could not share with %s: %s", form_id, email, exc)


def _google_form(survey: Survey) -> tuple[str, str]:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise FormsError("Google Forms credentials are not configured.")
    try:
        info = json.loads(raw)
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
        import httpx

        creds = Credentials.from_service_account_info(info, scopes=FORM_SCOPES)
        creds.refresh(Request())
        headers = {"Authorization": f"Bearer {creds.token}"}
        with httpx.Client(timeout=10) as client:
            created = client.post(
                "https://forms.googleapis.com/v1/forms", headers=headers,
                json={"info": {"title": survey.title, "documentTitle": f"ViewBox - {survey.title}",
                               "description": survey.description or ""}})
            created.raise_for_status()
            form_id = created.json()["formId"]
            updates = []
            for index, (label, required) in enumerate(_questions(survey)):
                updates.append({
                    "addItem": {
                        "location": {"index": index},
                        "item": {"title": label, "questionItem": {"question": {
                            "required": required, "textQuestion": {"paragraph": False}}}},
                    }
                })
            response = client.post(
                f"https://forms.googleapis.com/v1/forms/{form_id}:batchUpdate", headers=headers,
                json={"requests": updates, "includeFormInResponse": True})
            response.raise_for_status()
            form = response.json().get("form", {})
            _share_form(client, headers, form_id)
        return form_id, form.get("responderUri") or f"https://docs.google.com/forms/d/{form_id}/viewform"
    except FormsError:
        raise
    except Exception as exc:
        raise FormsError(f"Google Forms refused the request: {exc}") from exc


def create_form(db: Session, survey: Survey) -> dict:
    """Create the matching Google Form once; a local mock link is used without credentials."""
    if survey.google_form_id:
        return {"form_id": survey.google_form_id, "url": survey.google_form_url,
                "mode": survey.google_form_mode or "mock", "questions": len(_questions(survey))}
    try:
        form_id, url = _google_form(survey)
        mode = "live"
    except FormsError as exc:
        log.info("using local Google Form link for survey %s: %s", survey.id, exc)
        form_id = f"mock-{survey.id}-{secrets.token_hex(3)}"
        url = f"https://docs.google.com/forms/d/e/{form_id}/viewform"
        mode = "mock"
    survey.google_form_id = form_id
    survey.google_form_url = url
    survey.google_form_mode = mode
    db.commit()
    return {"form_id": form_id, "url": url, "mode": mode, "questions": len(_questions(survey))}


def _source(db: Session) -> Source:
    source = db.query(Source).filter_by(name=GOOGLE_FORM_SOURCE).first()
    if source:
        return source
    base, slug, n = "google-form", "google-form", 2
    while db.query(Source).filter_by(unique_slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    source = Source(name=GOOGLE_FORM_SOURCE, type="google_form", unique_slug=slug)
    db.add(source)
    db.flush()
    return source


def ingest_response(db: Session, payload: dict) -> dict:
    """Store one Google Form response as a Google Form lead in the shared dashboard."""
    response_id = str(payload.get("response_id") or "").strip()
    if not response_id:
        raise FormsError("A response_id is required for every Google Form response.")
    existing = db.query(GoogleFormLead).filter_by(response_id=response_id).first()
    if existing:
        return {"status": "duplicate", "lead_id": existing.id, "member_id": existing.member_id}

    fields = _flatten_fields(payload.get("fields") or payload.get("answers") or {})
    name = _pick(fields, "name", "full name", "full_name", "fullName")
    phone_raw = _pick(fields, "phone", "phone number", "phone_number", "mobile", "mobile number")
    city = _pick(fields, "city")
    email = _pick(fields, "email", "email address")
    income = _pick(fields, "income", "income range")
    interests = _pick(fields, "interests")

    form_id = payload.get("form_id") or _pick(fields, "form_id", "form id")
    survey_id = payload.get("survey_id") or _pick(fields, "survey_id", "survey id")
    survey = db.get(Survey, int(survey_id)) if survey_id else None
    if not survey and form_id:
        survey = db.query(Survey).filter_by(google_form_id=str(form_id)).first()

    problem = None
    phone = None
    if not survey:
        problem = "This Google Form is not linked to an active ViewBox survey."
    if not name:
        problem = "The form response is missing a full name."
    if not phone_raw:
        problem = "The form response is missing a phone number."
    else:
        try:
            phone = normalize_phone(phone_raw)
        except FormsError as exc:
            problem = str(exc)

    lead = GoogleFormLead(
        response_id=response_id, form_id=form_id or (survey.google_form_id if survey else None),
        survey_id=survey.id if survey else None, name=str(name).strip()[:120] if name else None,
        phone=phone, city=str(city).strip()[:80] if city else None,
        email=str(email).strip()[:160] if email else None,
        answers_json=json.dumps(fields, default=str), source=GOOGLE_FORM_SOURCE,
        status="Lead" if not problem else "needs review", received_at=datetime.utcnow())
    db.add(lead)
    db.flush()

    if not problem:
        source = _source(db)
        member = db.query(Member).filter_by(phone=phone).first()
        if not member:
            member = Member(phone=phone, name=str(name).strip().title()[:80],
                            city=str(city).strip()[:60] if city else None,
                            income_range=str(income).strip()[:40] if income else None,
                            interests=str(interests).strip()[:300] if interests else "",
                            source_id=source.id, first_touch_source_id=source.id)
            db.add(member)
            db.flush()
            db.add(Referral(referred_member_id=member.id))
        lead.member_id = member.id

    db.commit()
    path = sync_xlsx(db)
    if problem:
        raise FormsError(problem)
    return {"status": "created", "lead_id": lead.id, "member_id": lead.member_id,
            "survey_id": lead.survey_id, "source": GOOGLE_FORM_SOURCE, "xlsx": str(path)}


def list_leads(db: Session, limit: int = 100) -> list[dict]:
    out = []
    for lead in db.query(GoogleFormLead).order_by(GoogleFormLead.id.desc()).limit(limit).all():
        survey = db.get(Survey, lead.survey_id) if lead.survey_id else None
        out.append({"id": lead.id, "response_id": lead.response_id, "form_id": lead.form_id,
                    "survey": survey.title if survey else None, "name": lead.name,
                    "phone": lead.phone, "city": lead.city, "email": lead.email,
                    "source": lead.source or GOOGLE_FORM_SOURCE, "status": lead.status,
                    "member_id": lead.member_id,
                    "received_at": lead.received_at.isoformat() if lead.received_at else None})
    return out


def xlsx_rows(db: Session) -> list[dict]:
    rows = []
    for lead in db.query(GoogleFormLead).order_by(GoogleFormLead.id).all():
        survey = db.get(Survey, lead.survey_id) if lead.survey_id else None
        rows.append({"id": lead.id, "response_id": lead.response_id, "form_id": lead.form_id,
                     "survey": survey.title if survey else "", "name": lead.name or "",
                     "phone": lead.phone or "", "city": lead.city or "", "email": lead.email or "",
                     "status": lead.status, "source": lead.source or GOOGLE_FORM_SOURCE,
                     "received_at": lead.received_at.isoformat() if lead.received_at else ""})
    return rows


def _workbook(rows: list[dict]) -> BytesIO:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Google Form Leads"
    ws.append(XLSX_FIELDS)
    for row in rows:
        ws.append([row.get(field, "") for field in XLSX_FIELDS])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_xlsx(db: Session) -> BytesIO:
    return _workbook(xlsx_rows(db))


def sync_xlsx(db: Session) -> Path:
    """Keep the repository's own .xlsx file in step with every captured response."""
    rows = xlsx_rows(db)
    configured = os.getenv("GOOGLE_FORM_XLSX_PATH")
    path = Path(configured) if configured else Path(__file__).resolve().parents[2] / "data" / "google_form_leads.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_workbook(rows).getvalue())
    sheets.log_sync(db, "google_form_leads", "push", "ok", row_count=len(rows))
    return path


def _open_responses_sheet():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("GOOGLE_FORM_RESPONSES_SHEET_ID") or os.getenv("SPREADSHEET_ID")
    if not raw or not sheet_id:
        raise FormsNotConfigured("Google Form response sync is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON "
                                 "and GOOGLE_FORM_RESPONSES_SHEET_ID.")
    try:
        info = json.loads(raw)
        from google.oauth2.service_account import Credentials
        import gspread

        creds = Credentials.from_service_account_info(info, scopes=sheets.SCOPES)
        return gspread.authorize(creds).open_by_key(sheet_id)
    except FormsError:
        raise
    except Exception as exc:
        raise FormsError(f"Google Sheets refused the request: {exc}") from exc


def _local_responses_path() -> Path:
    configured = os.getenv("GOOGLE_FORM_RESPONSES_LOCAL_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "data" / "google_form_responses.csv"


def _read_local_responses(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise FormsError(f"Could not read local Google Form responses: {exc}") from exc


def sync_from_sheet(db: Session) -> dict:
    """Pull response rows from the linked Sheet or local demo CSV into the shared dashboard and .xlsx."""
    mode = "sheet"
    try:
        sheet = _open_responses_sheet()
    except FormsNotConfigured as exc:
        log.info("using local Google Form responses: %s", exc)
        sheet = None
        mode = "local"

    if sheet is None:
        records = _read_local_responses(_local_responses_path())
    else:
        worksheet = os.getenv("GOOGLE_FORM_RESPONSES_WORKSHEET", "Form Responses 1")
        try:
            ws = sheet.worksheet(worksheet)
        except Exception:
            ws = sheet.sheet1
        records = ws.get_all_records()

    linked = db.query(Survey).filter(Survey.google_form_id != None).all()
    default_survey = linked[0] if len(linked) == 1 else None
    if mode == "local" and default_survey is None:
        default_survey = db.query(Survey).order_by(Survey.id).first()
    created = duplicates = 0
    errors = []
    for record in records:
        fields = _flatten_fields(record)
        response_id = _pick(fields, "response id", "response_id") or _pick(fields, "timestamp")
        if not response_id:
            response_id = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()[:16]
        survey_id = _pick(fields, "survey_id", "survey id")
        if survey_id:
            try:
                survey_id = int(survey_id)
            except (TypeError, ValueError):
                errors.append("A response row has an invalid survey_id.")
                continue
        payload = {"response_id": str(response_id), "fields": fields,
                   "form_id": _pick(fields, "form_id", "form id") or
                              (default_survey.google_form_id if default_survey else None),
                   "survey_id": survey_id}
        try:
            result = ingest_response(db, payload)
            if result["status"] == "duplicate":
                duplicates += 1
            else:
                created += 1
        except FormsError as exc:
            errors.append(str(exc))
    path = sync_xlsx(db)
    sheets.log_sync(db, "google_form_leads", "pull", "ok", row_count=len(records))
    return {"synced": created, "duplicates": duplicates, "failed": len(errors),
            "errors": errors[:10], "xlsx": str(path), "mode": mode}


def verify_webhook(body: bytes, signature: str | None) -> None:
    secret = os.getenv("GOOGLE_FORMS_WEBHOOK_SECRET")
    if not secret:
        return
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise FormsError("Invalid Google Forms webhook signature.")
