# ViewBox - Master Checklist
Legend: [x] done in current repo, [ ] to do. Priority: **P0** must (core/scoring), **P1** should, **P2** bonus.
Scoring: Thinking 30% - UI/UX 30% - Code 20% - Git and Docs 20%. A flawless core beats many extras.

## 1. Fix the core first (P0)
- [x] Mock OTP login + 5 attempts / 10 min limit
- [x] Sources stored as data; admin adds a source from the UI
- [x] HMAC-signed `?src=` / `?ref=` links; forged links ignored with a message
- [x] "How did you hear about us?" fallback
- [x] Eligibility engine: age/city/gender/income, Strict/Flexible, quota, deadline, plain-language reasons
- [x] Referral stages, failure reason, masked phone on referrer dashboard
- [x] Grid search-as-you-type, filters, CSV export of the current view
- [x] Source dashboard (sign-ups / Fit / Completed)
- [x] Messy CSV import never crashes, reports counts + reasons
- [x] `POST /api/meta/lead` with dedupe + invalid handling
- [x] **FIXED: marking "Completed" must write a `completions` row** (ask which survey + quality check passed), so the 3-month cool-off really triggers
- [x] **Admin UI to create surveys + rules** (title, deadline, quota, amount, rules with Strict/Flexible)
- [x] Profile as its own step right after first login (brief: "filled once after first login")
- [x] Save every computed result to `eligibility_results`
- [x] Grid status filter also supports Approved / Rejected / Waitlisted (per survey)
- [x] Excel (.xlsx) export in addition to CSV (openpyxl)
- [x] Test with the REAL `viewbox_respondents_sample.csv` (~200 rows); fix parser for its actual mess (dates, phones, gender, duplicates, blank rows, encoding)
- [x] First touch vs last touch: first-seen link kept in browser, sent as `first_src`; `source_id` = last touch, `first_touch_source_id` = first touch (no separate touch log yet)
- [x] Source-conflict case verified: Instagram link + typed referrer => source Instagram, referrer credited
- [x] Typed referrer on the fallback form (matched by exact phone number, not ambiguous names)
- [x] Member status screen shows Fit/Completed state + payment/bonus status so they need not call the team

## 2. UI/UX - 30% of score (P0)
For EVERY screen confirm empty, loading and error states: 
- [ ] Phone/OTP  - [ ] Profile  - [ ] Home/surveys  - [ ] My referrals  - [ ] Admin login  - [ ] Grid  - [ ] Sources  - [ ] Source stats  - [ ] Import  - [ ] Survey create
- [ ] Test at 360px wide phone and desktop; no sideways page scroll (tables scroll inside their box)
- [ ] Touch targets >= 44px, visible focus, labels on every input, contrast checked (light + dark)
- [ ] Inline field errors in plain words (no raw JSON / stack traces)
- [ ] Success feedback (toast / banner) after add source, stage change, import
- [ ] Copy-to-clipboard button for referral link and source links
- [ ] Sticky filter bar + obvious "Export current view" button on admin grid
- [ ] Consistent spacing/type/colour tokens (one design system)
- [x] Replace `prompt()` / `alert()` for Fail reason with a small modal
- [ ] Optional: port to React + Vite + Tailwind ONLY if core is finished (risk vs reward: vanilla is acceptable)

## 3. Code quality - 20% (P0/P1)
- [ ] Split `main.py` into `routers/` (auth, member, admin, import, meta), `schemas/`, `services/` (eligibility, import, referral), `utils/`
- [ ] Frontend folders: components, pages, hooks, api (or split JS modules)
- [ ] Pydantic validation on every endpoint (check each one, incl. query params)
- [ ] pytest suite: eligibility (each outcome + cool-off), HMAC verify/forgery, OTP rate limit, import messy rows, Meta dedupe/invalid, auth required on admin routes
- [ ] Logging for skipped rows / errors; friendly message to the user
- [ ] Pin versions in `requirements.txt`; seed script idempotent
- [ ] Remove dead code, add short docstrings where the logic is non-obvious
- [ ] `.env.example` complete; confirm no secrets or `.db` committed

## 4. Security posture (implement + document; never say "unhackable")
- [x] SQLAlchemy parameterised queries, Pydantic validation, HMAC links, OTP limit, admin auth, CORS restricted, phone masking
- [ ] Meta endpoint: verify a shared token / `X-Hub-Signature-256` header
- [ ] Rate limit signup/IP (needed for fraud signal too)
- [ ] Check admin routes all require auth (write a test that loops all `/api/admin/*`)
- [ ] README: production list - Postgres, Redis (sessions/OTP), HTTPS, middleware rate limiting, audit logs, RBAC, CSP/HSTS

## 5. Bonus Tier 2 (only after sections 1-4) - suggested order
1. [ ] Import preview + per-row error report (preview BEFORE saving)
2. [ ] Admin manual override Waitlisted -> Approved with reason (endpoint + UI + logged)
3. [ ] Fraud flags + review queue: same phone twice, self-referral, referral ring A<->B, many signups from one IP; never auto-delete
4. [ ] Payout ledger: amount per completed survey + successful referral; ops approves each before Paid
5. [ ] Meta leads admin view + per-campaign breakdown

## 6. Tier 3 - pick exactly ONE
- [ ] (a) ML completion-likelihood badge  or (b) LLM rule suggestion with admin edit + approve (never auto-save)  or (c) Razorpay sandbox payout
- Suggested: (b), it fits the "deterministic and auditable" rule best

## 7. README - exact 9 sections
- [ ] 1 Overview (3-4 lines)  - [ ] 2 Tech stack  - [ ] 3 Setup (test it on a clean machine, < 5 min)  - [ ] 4 Demo logins + test data
- [ ] 5 Features marked Done / Partly done / Not done (be honest; re-check at the end)
- [ ] 6 Database design + link to /design  - [ ] 7 Endpoints each with method, URL, purpose, sample request + response
- [ ] 8 Decisions: source conflict, first vs last touch, payment gateway plan (Razorpay: approve -> API -> capture -> webhook -> Paid; failures via retries + polling) + security posture
- [ ] 9 Known issues + Tier 4 roadmap (ML analytics/forecasting, Postgres/Redis, production payments, LLM factors, audit logs, RBAC, security headers)
- [ ] Meta research paragraph: real lead ads send a webhook with a lead ID, then you fetch the form fields from Meta's Graph API; this mock accepts the fields directly

## 8. /design folder (by end of Day 2)
- [x] User flow + DB diagram (PNG/SVG)  - [ ] Add "Create survey" screen only if built, otherwise remove from flow BEFORE Day 2
- [ ] After Day 2: never edit; add new files (e.g. `design/03_changes_day5.md`)

## 9. Git - 20% (do not push once at the end)
Re-create history in small commits over the days, for example:
- Day 1: scaffold, models, design  - Day 2: auth/OTP, sources, signed links, push + email
- Day 3: signup + profile + eligibility engine  - Day 4: referrals + admin grid/export + dashboard
- Day 5: CSV import, Meta endpoint, UI states, tests  - Day 6: Tier 2 items  - Day 7: Tier 3, README, video
- [ ] Meaningful messages (`feat:`, `fix:`, `docs:`, `test:`), real author name/email, public repo

## 10. Walkthrough video (3-5 min)
- [ ] 0:00 run from scratch (clone, install, seed, start)  - [ ] 0:45 member flow via a source link, OTP, profile, surveys, eligibility reasons
- [ ] 1:45 referral flow: referrer link -> friend signs up -> ops marks Fit/Completed -> referrer sees stage
- [ ] 2:30 admin: search/filter/export, source dashboard, CSV import report, Meta endpoint call
- [ ] 3:30 explain DB design, first vs last touch, source-vs-referrer decision, security + what you did not build

## 11. Final QA before sending
- [ ] Fresh `git clone` into a new folder, follow README exactly, timed < 5 min
- [ ] Demo data present on first run; demo logins work
- [ ] Test matrix: age 17 / 40, wrong city (strict vs flexible), full quota, past deadline, cool-off date, duplicate phone, forged link, bad CSV row, duplicate Meta lead
- [ ] No secrets, `.env`, `.db` or `__pycache__` in repo
- [ ] Day 2 email: repo link + /design done  - [ ] Day 7 email: same repo link + video link
- [ ] To miloni@concaveinsights.com, CC genis@concaveinsights.com; Subject: `Technical Assessment - <Your Name> - ViewBox Panel System`
