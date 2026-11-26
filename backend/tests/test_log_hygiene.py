import asyncio
import json
import logging
import re

from app.main import friendly
from app.models import AuditEvent, SessionLocal
from app.services import audit


def test_audit_name_newline_does_not_create_second_log_line():
    event_id = audit.log(None, "admin", "test_action", "test",
                         details={"name": "A\nB\rC", "phone": "9821111111", "otp": "123456"})
    db = SessionLocal()
    try:
        details = db.get(AuditEvent, event_id).details_json
    finally:
        db.close()
    assert "\n" not in details and "\r" not in details
    assert "9821111111" not in details
    assert "123456" not in details
    assert "ABC" in details


def test_exception_handler_is_generic_with_correlation_id(caplog):
    exc = RuntimeError("phone=9821111111 otp=123456 token=abc body=secret")
    with caplog.at_level(logging.ERROR, logger="viewbox"):
        response = asyncio.run(friendly(None, exc))
    body = response.body.decode()
    data = json.loads(body)
    assert response.status_code == 500
    assert re.fullmatch(r"[0-9a-f-]{36}", data["correlation_id"])
    assert data["correlation_id"] in caplog.text
    assert "RuntimeError" in caplog.text
    assert "Traceback" not in caplog.text
    for secret in ("9821111111", "123456", "abc", "secret"):
        assert secret not in body
        assert secret not in caplog.text
