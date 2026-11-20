import base64, hashlib, hmac, json, os, secrets, time
from fastapi import HTTPException

SECRET = os.getenv("APP_SECRET", "dev-secret-change-me").encode()

def _sig(s: str) -> str:
    return hmac.new(SECRET, s.encode(), hashlib.sha256).hexdigest()[:24]

def sign_link(kind: str, value: str) -> str:
    return f"{value}.{_sig(kind + ':' + value)}"

def verify_link(kind: str, token: str | None):
    """Return the value if the HMAC is valid, else None."""
    try:
        value, sig = (token or "").rsplit(".", 1)
    except ValueError:
        return None
    return value if hmac.compare_digest(sig, _sig(kind + ":" + value)) else None

def make_token(sub, role: str, ttl=86400) -> str:
    p = base64.urlsafe_b64encode(json.dumps({"sub": sub, "role": role, "exp": time.time() + ttl}).encode()).decode()
    return f"{p}.{_sig(p)}"

def read_token(tok: str):
    try:
        p, sig = tok.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sig(p)): return None
        d = json.loads(base64.urlsafe_b64decode(p))
        return d if d["exp"] > time.time() else None
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

def mask(phone: str) -> str:
    return phone[:2] + "X" * 6 + phone[-2:] if phone and len(phone) >= 4 else "XXXX"
