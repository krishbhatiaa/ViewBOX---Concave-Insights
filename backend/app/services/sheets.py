"""Google Sheets sync helpers: push the member grid, pull rows through CSV import."""
import csv
import io
import json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import SheetSyncLog
from . import grid, importer

log = logging.getLogger("viewbox.sheets")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetSyncError(Exception):
    """Human-readable Google API failure surfaced as a 502 by the router."""


def _open_sheet():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("SPREADSHEET_ID")
    if not raw or not sheet_id:
        raise SheetSyncError("Google Sheets is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON and SPREADSHEET_ID.")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SheetSyncError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
    try:
        from google.oauth2.service_account import Credentials
        import gspread
    except ImportError as exc:
        raise SheetSyncError("Google Sheets libraries are not installed on the server.") from exc
    try:
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds).open_by_key(sheet_id)
    except Exception as exc:
        raise SheetSyncError(f"Google Sheets refused the request: {exc}") from exc


def log_sync(db: Session, entity_type: str, direction: str, status: str,
             row_count: int | None = None, error: str | None = None) -> SheetSyncLog:
    row = SheetSyncLog(entity_type=entity_type, direction=direction, status=status,
                       row_count=row_count, error_text=error, synced_at=datetime.utcnow())
    db.add(row)
    db.commit()
    return row


def status(db: Session, entity_type: str = "members") -> dict:
    """Last push/pull times, row count and error for the admin status card."""
    rows = db.query(SheetSyncLog).filter_by(entity_type=entity_type).order_by(SheetSyncLog.id.desc()).all()
    last = rows[0] if rows else None
    return {
        "last_push": next((r.synced_at.isoformat() for r in rows if r.direction == "push"), None),
        "last_pull": next((r.synced_at.isoformat() for r in rows if r.direction == "pull"), None),
        "status": last.status if last else "never",
        "row_count": last.row_count if last and last.row_count is not None else 0,
        "error": last.error_text if last else None,
    }


def push(db: Session, filters: dict) -> dict:
    rows = grid.grid_rows(db, **filters)
    fields = grid.export_fields(filters.get("survey_id"))
    rows = grid.flatten([dict(r) for r in rows])
    name = f"Export_{datetime.utcnow():%Y%m%d_%H%M}"
    try:
        sheet = _open_sheet()
        ws = sheet.add_worksheet(title=name, rows=max(len(rows) + 1, 2), cols=max(len(fields), 1))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
        url = getattr(sheet, "url", "")
    except SheetSyncError:
        log_sync(db, "members", "push", "error")
        raise
    except Exception as exc:
        log_sync(db, "members", "push", "error", error=str(exc)[:500])
        raise SheetSyncError(f"Could not write to Google Sheets: {exc}") from exc
    log_sync(db, "members", "push", "ok", row_count=len(rows))
    return {"sheet": ws.title, "url": url, "rows": len(rows)}


def pull_records(db: Session, records: list, worksheet: str = "sheet1") -> dict:
    """Feed worksheet rows through the same importer used by CSV uploads."""
    if not isinstance(records, list):
        raise SheetSyncError("Google Sheets returned an unexpected row format.")
    keys = sorted({str(k) for row in records if isinstance(row, dict) for k in row})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys)
    writer.writeheader()
    for row in records:
        writer.writerow({k: (row.get(k, "") if isinstance(row, dict) else "") for k in keys})
    summary = importer.run_import(db, buf.getvalue(), f"Google Sheets: {worksheet}", dry_run=False)
    if summary is None:
        raise SheetSyncError("The worksheet has no rows to import.")
    log_sync(db, "members", "pull", "ok", row_count=summary["total_rows"])
    return {"total": summary["total_rows"], "imported": summary["imported"],
            "fixed": summary["fixed"], "skipped": summary["skipped"], "details": summary["details"]}


def pull(db: Session, worksheet: str = "sheet1") -> dict:
    try:
        sheet = _open_sheet()
        ws = sheet.sheet1 if worksheet in ("", "sheet1", None) else sheet.worksheet(worksheet)
        records = ws.get_all_records()
    except SheetSyncError:
        log_sync(db, "members", "pull", "error")
        raise
    except Exception as exc:
        log_sync(db, "members", "pull", "error", error=str(exc)[:500])
        raise SheetSyncError(f"Could not read Google Sheets: {exc}") from exc
    return pull_records(db, records, worksheet)
