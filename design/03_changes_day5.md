# Changes after Day 2 (new file — `01_user_flow.md` and `02_database.md` stay frozen)

## 1. Screens added to the flow since Day 2

The Day-2 user flow (`01_user_flow.md`) predates these admin screens, which now exist:

```
M[Admin login]
  --> N[Grid: search, filter, export CSV/Excel]
  --> O[Sources + signed links]
  --> P[Mark Fit / Completed / Failed]
  --> Q[Source dashboard]
  --> R[CSV import + report]
  --> U[Create survey + rules]        <-- added after Day 2 (was only in the brief)
  --> V[Payout ledger: Pending -> Approved -> Paid]
  --> W[Fraud flag review queue]
  --> X[Meta leads + per-campaign breakdown]   <-- added Day 5+
```

No schema change: surveys/rules already existed in `02_database.md`; the *screen*
to create them was built later.

## 2. Day-5+ changes

| Change | Where |
|---|---|
| `POST /api/admin/suggest-rules` — LLM (or offline keyword) eligibility-rule suggestions; returns candidates only, admin edits then saves via the normal create-survey form | `backend/app/services/rule_suggest.py`, `routers/admin.py` |
| New env keys `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (commented-out, optional; feature degrades to heuristic when unset) | `backend/.env.example` |
| Meta leads admin view: `GET /api/admin/meta-leads` (list) + `GET /api/admin/meta-leads/stats` (per-campaign / per-ad counts) | `routers/admin.py`, `frontend/src/pages/admin/MetaLeadsPage.jsx` |
| UI/UX pass: Profile link-resolve loading/error states, ≥44px touch targets, grid sticky filter bar with in-bar "Export current view", measured sticky header offset (`--admin-header-h`), contrast fixes, shared colour tokens (`@theme`, `TONES`/`BAR_TONES`), `Input` forwards refs (fixes CSV file-input reset) | `frontend/src/**` |

## 3. Unchanged decisions

First vs last touch, source-vs-referrer conflict, HMAC link signing and the
Meta webhook verification are unchanged from Day 2 — see README §8.
