"""Public webhook for Google Form responses pushed by an Apps Script or the local simulator."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from ..deps import db_dep
from ..schemas import GoogleFormLeadIn
from ..services import google_forms

router = APIRouter()


@router.post("/api/google-forms/lead")
async def google_form_lead(request: Request, db=Depends(db_dep)):
    body = await request.body()
    try:
        google_forms.verify_webhook(body, request.headers.get("X-Google-Forms-Signature-256"))
    except google_forms.FormsError as exc:
        raise HTTPException(403, str(exc))
    try:
        payload = json.loads(body or b"{}")
        data = GoogleFormLeadIn(**payload).model_dump()
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(422, "Please send a valid Google Form response with a response_id.")
    try:
        return google_forms.ingest_response(db, data)
    except google_forms.FormsError as exc:
        raise HTTPException(422, str(exc))
