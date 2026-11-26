"""FastAPI app factory: middleware, database bootstrap, routers, SPA fallback.

All routes live in app/routers/, validation schemas in app/schemas.py,
business logic in app/services/ (see those modules for the actual behaviour).
"""
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .models import Base, engine
from .routers import admin, auth, importer, member, meta
from .services.ratelimit import rate_limiter, warn_if_inmemory_multiworker

log = logging.getLogger("viewbox")

# CORS: FRONTEND_URL may be comma-separated (e.g. Vite dev server + built app)
_origins = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:8000").split(",") if o.strip()]
_origins += ["http://localhost:5173", "http://127.0.0.1:5173"]

warn_if_inmemory_multiworker(rate_limiter, int(os.getenv("WEB_CONCURRENCY", os.getenv("WORKERS", "1"))))

app = FastAPI(title="ViewBox Panel System")
app.add_middleware(CORSMiddleware, allow_origins=list(dict.fromkeys(_origins)),
                   allow_methods=["*"], allow_headers=["*"])

Base.metadata.create_all(engine)


def _ensure_columns():
    """SQLite has no ALTER COLUMN: add columns introduced after a table was created."""
    from sqlalchemy import inspect, text
    want = {"members": {"ip": "VARCHAR", "device_id": "VARCHAR"},
            "fraud_flags": {"reviewed_by": "VARCHAR", "reviewed_at": "DATETIME"},
            "sheet_sync_log": {"row_count": "INTEGER"},
            "referrals": {"channel": "VARCHAR"}}
    insp = inspect(engine)
    with engine.begin() as conn:
        for name in ("audit_events", "sheet_sync_log", "touch_events"):
            Base.metadata.tables[name].create(bind=conn, checkfirst=True)
        for table, cols in want.items():
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, typ in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
        indexes = {
            "eligibility_results": "CREATE UNIQUE INDEX IF NOT EXISTS uq_elig_member_survey "
                                   "ON eligibility_results (member_id, survey_id)",
            "admin_overrides": "CREATE UNIQUE INDEX IF NOT EXISTS uq_override_member_survey "
                               "ON admin_overrides (member_id, survey_id)",
        }
        tables = set(insp.get_table_names())
        for table, stmt in indexes.items():
            if table in tables:
                conn.execute(text(stmt))


_ensure_columns()


@app.exception_handler(Exception)
async def friendly(_, exc):
    log.exception("unhandled")
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, 500)


for r in (auth.router, member.router, admin.router, importer.router, meta.router):
    app.include_router(r)

# ---------- frontend (SPA: every non-API GET serves the built app, so deep links work) ----------
_DIST = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
_INDEX = os.path.join(_DIST, "index.html")
if not os.path.isfile(_INDEX):  # dev fallback: the Vite shell (served behind `npm run dev`)
    _INDEX = os.path.join(_DIST, "..", "index.html")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    candidate = os.path.normpath(os.path.join(_DIST, full_path))
    # hashed assets, favicon, etc. must stay inside dist (no path traversal)
    if (candidate == _DIST or candidate.startswith(_DIST + os.sep)) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(_INDEX)
