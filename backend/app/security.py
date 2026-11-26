import base64, hashlib, hmac, json, os, secrets, time
from fastapi import HTTPException

from .services.ratelimit import rate_limiter

SECRET = os.getenv("APP_SECRET", "dev-secret-change-me").encode()
ALLOWED_ALGORITHMS = ["HS256"]
TOKEN_ROLES = ("member", "admin")
CLOCK_SKEW_SECONDS = 30

def sanitize_param(value: str | None, limit: int = 64) -> str:
    """Strip CRLF/semicolon/NUL from a user-supplied attribution value."""
    return str(value or "").replace("\r", "").replace("\n", "").replace(";", "").replace("\x00", "")[:limit]

def _sig(s: str) -> str:
    return hmac.new(SECRET, s.encode(), hashlib.sha256).hexdigest()[:24]

def sign_link(kind: str, value: str) -> str:
    clean = sanitize_param(value)
    return f"{clean}.{_sig(kind + ':' + clean)}"

def verify_link(kind: str, token: str | None):
    """Return the sanitized value if the HMAC is valid, else None."""
    try:
        value, sig = sanitize_param(token, 128).rsplit(".", 1)
    except ValueError:
        return None
    value = sanitize_param(value)
    return value if hmac.compare_digest(sig, _sig(kind + ":" + value)) else None

def make_token(sub, role: str, ttl=86400) -> str:
    payload = {"alg": "HS256", "sub": sub, "role": role, "exp": time.time() + ttl}
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{p}.{_sig(p)}"

def read_token(tok: str):
    try:
        p, sig = tok.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sig(p)): return None
        d = json.loads(base64.urlsafe_b64decode(p))
        if d.get("alg") not in ALLOWED_ALGORITHMS: return None
        if d.get("sub") in (None, "") or d.get("role") not in TOKEN_ROLES: return None
        exp = float(d["exp"])
        if time.time() - CLOCK_SKEW_SECONDS >= exp: return None
        return d
    except Exception:
        return None

def hash_pw(pw: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()

def check_pw(pw: str, stored: str) -> bool:
    return hmac.compare_digest(hash_pw(pw, stored.split("$")[0]), stored)

_otps: dict = {}; _attempts: dict = {}

def issue_otp(phone: str) -> str:
    otp = f"{secrets.randbelow(10**6):06d}"
    _otps[phone] = (otp, time.time() + 300)
    return otp

def check_otp(phone: str, otp: str):
    """Rate limit: 5 attempts / 10 min per phone (in-memory; Redis in production)."""
    t = time.time(); a = [x for x in _attempts.get(phone, []) if t - x < 600]
    if len(a) >= 5:
        raise HTTPException(429, "Too many attempts. Please try again in 10 minutes.")
    _attempts[phone] = a + [t]
    rec = _otps.get(phone)
    if not rec or rec[1] < t or rec[0] != otp:
        raise HTTPException(400, "That OTP is incorrect or has expired. Please request a new one.")
    _otps.pop(phone, None)
    _attempts.pop(phone, None)

def mask(phone: str) -> str:
    return phone[:2] + "X" * 6 + phone[-2:] if phone and len(phone) >= 4 else "XXXX"

def reset_rate_limits():
    """Clear per-IP counters (used by tests; the default backend restarts with the process)."""
    if hasattr(rate_limiter, "reset"):
        rate_limiter.reset()

def enforce_ip_limit(request, bucket: str, limit: int | None = None, window: int = 3600):
    """Sliding-window rate limit per IP for a bucket such as 'otp' or 'signup'.

    Limit comes from SIGNUP_IP_LIMIT (default 60/hour per bucket). Raises 429.
    Uses the configured RateLimiter (in-memory by default, Redis for production).
    """
    limit = int(os.getenv("SIGNUP_IP_LIMIT", "60")) if limit is None else limit
    ip = ((request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else "unknown"))
    if not rate_limiter.allow(f"{bucket}:{ip}", limit, window):
        raise HTTPException(429, "Too many requests from this network. Please try again in an hour.")
