# Database diagram (frozen after Day 2)
```mermaid
erDiagram
  sources ||--o{ members : "source_id / first_touch_source_id"
  members ||--o{ members : "referrer_id"
  members ||--o{ referrals : "referred_member_id"
  members ||--o{ completions : has
  members ||--o{ eligibility_results : has
  members ||--o{ admin_overrides : has
  members ||--o{ fraud_flags : has
  members ||--o{ payouts : earns
  members ||--o| meta_leads : created_from
  surveys ||--o{ survey_rules : has
  surveys ||--o{ completions : has
  surveys ||--o{ eligibility_results : has
  surveys ||--o{ payouts : has
  referrals ||--o{ payouts : triggers
```
Extension: `referrals` holds one row per signup (referrer_id nullable) so ops can mark Fit/Completed for every member; this drives per-source Fit/Completed counts.
