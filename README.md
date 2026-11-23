# ViewBox Panel System — Concave Insights (technical assessment)

## 1. Project Overview
ViewBox records where every survey panel member comes from (signed source/referral links), credits the right referrer through Lead → Fit → Completed, checks survey eligibility with plain-language reasons (incl. 3-month cool-off), and lets members see their own status. Ops get a searchable grid with CSV export, a source dashboard, messy-CSV import and a Meta lead-ads endpoint.

## 2. Tech Stack
- Backend: **FastAPI** (chosen over Flask for built-in Pydantic validation on every endpoint, typed schemas and auto docs at `/docs`), SQLAlchemy 2, Uvicorn
- Frontend: single-file mobile-first HTML/CSS/JS (no build step; React + Vite + Tailwind port is on the roadmap)
- DB: SQLite. Libraries: pydantic, python-multipart, stdlib hmac/hashlib/csv

## 3. Setup and Run (~2 min)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional; defaults work locally
python -m app.seed              # loads demo data
uvicorn app.main:app --port 8000
```
Open http://localhost:8000 (UI) and http://localhost:8000/docs (API). Run from `backend/`.

## 4. Demo Logins and Test Data
- Admin: `admin@concave.test` / `admin123`
- Members (OTP is shown on screen): `9000000001` Priya (referrer), `…04` Karan (in cool-off), `…06` Anita (age 17 → Rejected), `…02`/`…03`/`…07` Priya's friends (Lead/Fit/Failed)
- New signup: copy a link from Admin → Sources (`/signup?src=…`) or Priya's referral link from her home page
- Messy import sample: `data/messy_sample.csv` (stand-in; use the real `viewbox_respondents_sample.csv` the same way)
- Meta sample: see section 7

## 5. Features
| Feature | Status |
|---|---|
| Mock OTP auth + profiles, OTP rate limit (5/10 min) | Done |
| Sources as data + HMAC-signed `?src=` / `?ref=` links | Done |
| "How did you hear about us?" fallback | Done |
| Eligibility engine (age/city/gender/income strict or flexible, quota, deadline) + reasons | Done |
| 3-month cool-off + re-eligibility date | Done |
| Referral stages, failure reason, referrer dashboard, masked phone | Done |
| Home with live surveys + interest highlight | Done |
| Admin grid: search-as-you-type, filters, CSV export of current view | Done (CSV only, no Excel) |
| Source dashboard (sign-ups / Fit / Completed) | Done |
| Messy CSV import with count + per-row reasons | Done |
| `POST /api/meta/lead` (dedupe, invalid flagged) | Done |
| Empty / loading / error states | Done (manually checked, no UI tests) |
| Fraud flags + review queue | Not done (tables exist) |
| Payout ledger / approval | Partly done (payout rows created on completion; approve -> paid enforced by API; no admin ledger screen) |
| Import preview before commit | Partly done (report after import) |
| Admin manual override | Partly done (eligibility honours overrides; no UI/endpoint) |
| Admin creates surveys + Strict/Flexible rules (UI) | Done |
| Ops marks Completed (survey + quality check) -> starts 3-month cool-off | Done |
| Member status panel (stage, completions, earnings) + referrer sees bonus status | Done |
| Meta leads admin view | Not done |
| Tier 3 "wow" feature | Not done |

## 6. Database Design
All tables from the brief exist in `backend/app/models.py`. Diagrams (PNG/SVG + Graphviz source) are in [`/design`](design/): ![user flow](design/user_flow.png) ![database](design/db_diagram.png)
One extension: `referrals` has one row per signup (nullable `referrer_id`) so ops can mark Fit/Completed for every member; `surveys.amount` was added for payouts.

## 7. API Endpoints
Interactive docs at `/docs`. Key ones:
| Method | URL | Purpose |
|---|---|---|
| POST | `/api/otp/request` `{phone}` | Mock OTP → `{otp,is_member}` |
| POST | `/api/login`, `/api/signup` | Auth / create member (`src`,`ref`,`how_heard_source_id`) |
| GET | `/api/me`, `/api/surveys`, `/api/me/referrals` | Member portal (phones masked) |
| POST/GET | `/api/admin/login`, `/api/admin/sources` | Admin auth; sources + signed links |
| GET | `/api/admin/members?q=&source_id=&city=&status=` | Grid; `/export` returns same view as CSV |
| POST | `/api/admin/referrals/{id}/stage` | `{stage:"Completed",survey_id:1,quality_check_passed:true}` records completion, starts cool-off, creates payouts; `{stage:"Failed",failure_reason:"…"}` |
| GET/POST | `/api/admin/surveys` | List / create survey with rules |
| GET/POST | `/api/admin/payouts`, `/api/admin/payouts/{id}/status?status=Approved\|Paid` | Ops approval before Paid |
| GET | `/api/me/status` | Member's own stage, completions, earnings |
| GET | `/api/admin/source-stats` | Per-source funnel |
| POST | `/api/admin/import` | Multipart CSV → `{total_rows,imported,fixed,skipped,details[]}` |
| POST | `/api/meta/lead` | Meta lead ad |

Meta sample request → response:
```json
{"lead_id":"L1","form_id":"F1","campaign_id":"C9","ad_id":"A1","time":"2026-11-20T10:00:00Z",
 "fields":[{"name":"full_name","values":["Asha Rao"]},{"name":"phone_number","values":["+919822233344"]},{"name":"city","values":["Thane"]}]}
→ {"status":"created","member_id":14,"source":"Meta Ads","campaign_id":"C9"}
```
Repeat → `{"status":"duplicate"}`. Invalid phone/name → 422 (raw lead is stored for review). `fields` may also be a plain `{name,phone,city}` object.

## 8. Assumptions and Decisions
1. **Source conflict**: Instagram link + referrer → `source`=Instagram, `referrer_id`=member. Bonus goes to the referrer, source analytics to Instagram. A `?ref=` alone sets source to "Referral".
2. **First vs last touch**: the first signed link a visitor opens is remembered in the browser and sent as `first_src`; the link used at signup is `source_id` (last touch, for conversion). Both stored. Not done: a separate log of every visit.
3. **Payments**: Razorpay (UPI/cards/bank, sandbox). Ops approves → Orders/Payouts API → capture → webhook updates status → "Paid"; failed/pending handled by webhook retries + polling. Not built.
4. Cool-off = 90 days from last quality-passed completion. Invalid/forged links are ignored (signup still works) and the member is told.
5. Payout amounts: survey payment = `surveys.amount`; referral bonus = flat `REFERRAL_BONUS` (default 100, env). Cool-off starts only when the quality check passed; a failed quality check marks the stage Failed with a reason and creates no payout.
6. Pipeline stage is per signup row; "Failed" requires a reason.
**Security posture** (not "unhackable"): SQLAlchemy parameterised queries; Pydantic validation; HMAC-SHA256 signed links; OTP rate limit; signed expiring tokens with PBKDF2 admin passwords; admin routes protected; CORS limited to `FRONTEND_URL`; no secrets in repo; phones masked for members. Gaps: the Meta endpoint has no signature check, tokens are in localStorage, rate limit is per-phone only. Production: Postgres, Redis for sessions/OTP, HTTPS, middleware rate limiting, audit logs, RBAC, CSP/HSTS.




