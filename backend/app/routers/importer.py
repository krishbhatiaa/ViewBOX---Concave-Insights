"""CSV import endpoint: read the upload, plan it, report — dry_run previews without writing."""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..deps import admin_auth, db_dep
from ..services.importer import run_import

router = APIRouter()


@router.post("/api/admin/import")
async def import_csv(file: UploadFile = File(...), dry_run: bool = Query(False),
                     _=Depends(admin_auth), db: Session = Depends(db_dep)):
    try:
        text = (await file.read()).decode("utf-8-sig", errors="replace")
    except Exception:
        raise HTTPException(400, "Could not read this file.")
    summary = run_import(db, text, file.filename or "upload.csv", dry_run)
    if summary is None:
        raise HTTPException(422, "The file has no data rows.")
    return summary
