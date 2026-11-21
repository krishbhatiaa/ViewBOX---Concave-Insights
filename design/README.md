# /design
- `user_flow.png` / `.svg` - user flow of the main screens and steps 
- `db_diagram.png` / `.svg` - all tables, columns and relationships
- `*.dot` - Graphviz sources; `01_user_flow.md`, `02_database.md` - Mermaid versions

Frozen after Day 2: later design changes go in NEW files, never edit these.
Differences from the brief's schema: `surveys.amount` added (payout amount); `referrals` has one row per signup (`referrer_id` nullable) so ops can mark Fit/Completed for every member.
