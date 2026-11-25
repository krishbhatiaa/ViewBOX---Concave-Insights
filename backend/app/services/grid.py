"""Admin respondent grid: search/filter query, per-survey eligibility, CSV + Excel export."""
import csv
import io

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..eligibility import evaluate, record_result
from ..models import Member, Referral, Survey

ELIGIBILITY_STATUSES = ("Approved", "Rejected", "Waitlisted")  # per-survey results (need survey_id)
STAGE_STATUSES = ("Lead", "Fit", "Completed", "Failed", "flagged")
GRID_FIELDS = ["id", "name", "phone", "city", "gender", "source", "referrer", "stage",
               "created_at", "eligibility", "eligibility_reason"]


def member_query(db: Session, q, source_id, city, status):
    qs = db.query(Member)
    if q:
        conds = [Member.name.ilike(f"%{q}%"), Member.city.ilike(f"%{q}%")]
        if q.isdigit():
            conds.append(Member.id == int(q))
        qs = qs.filter(or_(*conds))
    if source_id:
        qs = qs.filter(Member.source_id == source_id)
    if city:
        qs = qs.filter(Member.city.ilike(city))
    if status == "flagged":
        qs = qs.filter(Member.is_flagged == True)
    elif status in ("Lead", "Fit", "Completed", "Failed"):
        qs = qs.filter(Member.id.in_(db.query(Referral.referred_member_id).filter(Referral.stage == status)))
    return qs.order_by(Member.id)


def grid_rows(db: Session, q="", source_id=None, city="", status="", survey_id=None):
    """Rows for the current search/filter view.

    When survey_id is given, every candidate member is evaluated against that survey,
    the result is saved to eligibility_results and returned as `eligibility`;
    status=Approved|Rejected|Waitlisted then narrows the view to that result.
    """
    if status and status not in ELIGIBILITY_STATUSES and status not in STAGE_STATUSES:
        raise HTTPException(422, f"Unknown status '{status}'. Pick a pipeline stage or, with a survey, a result.")
    survey = None
    if survey_id:
        survey = db.get(Survey, survey_id)
        if not survey:
            raise HTTPException(404, "Survey not found.")
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
            if status in ELIGIBILITY_STATUSES and res != status:
                continue
        out.append(row)
    if survey:
        db.commit()  # persist every computed result in one go
    return out


def flatten(rows):
    """Nested eligibility dicts -> flat columns for the spreadsheet."""
    for r in rows:
        e = r.pop("eligibility", None) or {}
        r["eligibility"] = e.get("result", "")
        r["eligibility_reason"] = e.get("reason", "")
    return rows


def export_fields(survey_id) -> list:
    return GRID_FIELDS if survey_id else [f for f in GRID_FIELDS if f not in ("eligibility", "eligibility_reason")]


def to_csv(rows, fields) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def to_xlsx(rows, fields) -> io.BytesIO:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Members"
    ws.append(fields)
    for r in rows:
        ws.append([r.get(k, "") for k in fields])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
