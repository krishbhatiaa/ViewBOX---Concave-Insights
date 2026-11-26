# Final Design Addendum

These changes were implemented after `01_user_flow.md` and `02_database.md` were frozen. Those two files are intentionally unchanged; this addendum is the only design update.

## 1. Interest-based survey matching

- Members and surveys both store interests as normalized comma-separated tags: trimmed, lowercased and de-duplicated.
- Admin survey create/edit now accepts an `Interests` field; the surveys table shows tags and an Edit action.
- The member home screen marks matching surveys as "Matches your interests" and lists the exact overlapping tags.
- Matching is case-insensitive, ignores empty interest lists and stable-sorts matching surveys first; non-matching surveys remain visible.
- Member signup already collected interests; imported/seeded members keep theirs as comma-separated text.

## 2. Admin referrals stage workflow

- A new Admin → Referrals screen lists `Lead / Fit / Completed / Failed` rows with search and stage filters.
- Ops can move a row to Fit with confirmation, to Completed after choosing a survey and passing the quality check, or to Failed with a required reason.
- `GET /api/admin/referrals` backs the screen; `POST /api/admin/referrals/{id}/stage` remains the only write path.
- Completed and Failed states appear on the member's own referrals screen, including the failure reason.

## 3. Profile collection timing

- Profile is still collected immediately after first OTP verification, before the member account is created.
- `GET /api/me` now returns `profile_complete` plus the profile fields needed to prefill an edit form.
- `MemberLayout` redirects any authenticated member whose profile is incomplete to `/profile`, even if the member came from seed or CSV import.
- `ProfilePage` supports both the fresh-signup pending flow and the existing-token edit flow, saving through `PATCH /api/me`.

## 4. 15-day survey cycle

- Admin create/edit rejects past deadlines and deadlines more than `SURVEY_MAX_CYCLE_DAYS` days from launch (default 15) with plain-language errors.
- The date inputs cap selectable dates and show the cycle rule; server validation messages appear inline under the deadline field.
- PATCH validates against the survey's original `created_at`, so older surveys are not retroactively invalidated when only status/quota/amount changes.
- The test helper creates surveys with relative deadlines; one legacy test writes an already-past deadline directly to the DB to keep the eligibility "closed" scenario covered.

## 5. Realistic Meta lead webhook

- `GET /webhooks/meta?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` returns the challenge as plain text only when the mode and `META_VERIFY_TOKEN` match; otherwise it returns 403.
- `POST /api/meta/lead` keeps the existing simple dev body and now also accepts a real Meta envelope: `entry[].changes[field=leadgen].value.leadgen_id`.
- For envelope leads, `LeadFetcher.fetch(leadgen_id)` returns `field_data` from the Graph API when `META_PAGE_ACCESS_TOKEN` is set, otherwise a mock fetcher returns fields so the local simulator still works.
- HMAC verification still covers the exact raw POST body when `META_WEBHOOK_SECRET` is set; duplicates, malformed envelopes, invalid fields and Graph failures produce plain-language responses.
- The simulator has a payload-format switch and a handshake test button, with the same response panel for both actions.

## Schema and migration note

- The only new persisted column is `surveys.interests` (`Text`, nullable). It is declared in `backend/app/models.py`, added to existing SQLite databases by `_ensure_columns()` in `backend/app/main.py`, and populated by `backend/app/seed.py`.
- No new tables, foreign keys or columns were added for Tasks 2–5; all other changes are request/response fields, validation, services and UI state.
