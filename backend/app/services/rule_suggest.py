"""Survey eligibility rule suggestions (Tier 3).

Never saves anything: returns candidate rules for the admin to edit and approve
in the normal "Create survey" form. Two sources:

* ``llm``     - an OpenAI-compatible chat completions API, when ``LLM_API_KEY`` is set.
* ``heuristic`` - deterministic keyword parsing of the title/description, used as a
  fallback so the feature also works offline / without a key.

Every candidate is validated through ``RuleIn``; anything that does not fit the
same shape the survey form accepts is dropped rather than passed through.
"""
import json
import os
import re

import httpx

from ..schemas import RuleIn

LLM_TIMEOUT = 15.0

_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Surat", "Kanpur", "Nagpur", "Indore",
    "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Chandigarh", "Kochi",
    "Coimbatore", "Gurgaon", "Gurugram", "Noida", "Faridabad", "Meerut", "Rajkot",
]

_SYSTEM = (
    "You suggest eligibility rules for market-research surveys. "
    "Reply with ONLY a JSON array (no prose, no markdown fence). Each element: "
    '{"rule_type": "age|city|gender|income", "value": "...", "strict_or_flexible": "strict|flexible"}. '
    "age value is a range like 18-35; city/gender/income values are comma lists "
    "(income must be one of: <5L, 5-10L, 10L+; gender one of: Male, Female, Other). "
    "Return an empty array if nothing can be inferred. Never invent rules the text does not support."
)


def _heuristic(title: str, description: str) -> list[dict]:
    text = f"{title} {description}".strip()
    low = text.lower()
    rules: list[dict] = []

    m = re.search(r"\b(\d{2})\s*(?:-|–|to|till|through)\s*(\d{2})\b", low)
    if m and 16 <= int(m[1]) < int(m[2]) <= 80:
        rules.append({"rule_type": "age", "value": f"{int(m[1])}-{int(m[2])}", "strict_or_flexible": "strict"})

    cities = [c for c in _CITIES if c.lower() in low]
    if cities:
        rules.append({"rule_type": "city", "value": ",".join(cities), "strict_or_flexible": "flexible"})

    if re.search(r"\b(women|woman|female|housewife|girls?)\b", low):
        rules.append({"rule_type": "gender", "value": "Female", "strict_or_flexible": "strict"})
    elif re.search(r"\b(men|man|male|boys?)\b", low):
        rules.append({"rule_type": "gender", "value": "Male", "strict_or_flexible": "strict"})

    inc = re.search(r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:l|lakh|lpa|k)", low)
    if inc:
        lo, hi = float(inc[1]), float(inc[2])
        allowed = []
        if lo < 5:
            allowed.append("<5L")
        if hi >= 5 and lo <= 10:
            allowed.append("5-10L")
        if hi > 10:
            allowed.append("10L+")
        if allowed:
            rules.append({"rule_type": "income", "value": ",".join(allowed), "strict_or_flexible": "flexible"})
    elif re.search(r"\b10\s*l|\b10l\+|high income|affluent\b", low):
        rules.append({"rule_type": "income", "value": "10L+", "strict_or_flexible": "flexible"})

    return rules


def _validate(candidates: list) -> list[dict]:
    """Keep only candidates that pass the same RuleIn validation the survey form uses."""
    out = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        try:
            out.append(RuleIn(**c).model_dump())
        except Exception:
            continue
    # de-duplicate on (type, value)
    seen, uniq = set(), []
    for r in out:
        key = (r["rule_type"], r["value"].lower())
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq


def _llm(title: str, description: str) -> list[dict] | None:
    """Ask an OpenAI-compatible API. Returns None when unavailable/disabled/failing."""
    key = os.getenv("LLM_API_KEY")
    if not key:
        return None
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    try:
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": f"Title: {title}\nDescription: {description or '(none)'}"},
                ],
            },
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else None
    except Exception:
        return None


def suggest_rules(title: str, description: str = "") -> dict:
    """Return ``{rules, source, note}`` — a suggestion only; nothing is persisted."""
    candidates = _llm(title, description)
    if candidates is not None:
        rules = _validate(candidates)
        if rules:
            return {"rules": rules, "source": "llm",
                    "note": "Suggested by AI — review every rule before creating the survey."}
        if candidates == []:  # model legitimately said "no rules"
            return {"rules": [], "source": "llm",
                    "note": "The AI could not infer any rules from that text — add them manually."}
    rules = _validate(_heuristic(title, description))
    note = ("Offline keyword suggestion (no LLM_API_KEY set or the call failed) — "
            "review before creating the survey.")
    return {"rules": rules, "source": "heuristic", "note": note}
