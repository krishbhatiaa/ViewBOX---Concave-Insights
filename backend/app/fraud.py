"""Fraud / duplicate detection.

Runs on every signup and on demand via POST /api/admin/fraud/scan.
Flags are never deleted: review sets them to Cleared or Confirmed.
"""
from datetime import datetime, timedelta
import ipaddress

from .models import FraudFlag, Member

BURST_MIN = 3          # sign-ups from one IP/device within BURST_WINDOW count as a burst
BURST_WINDOW = timedelta(hours=24)


def add_flag(db, member_id, flag_type, details) -> bool:
    """Open, idempotent flag. Returns True if a new flag row was created."""
    if db.query(FraudFlag).filter_by(member_id=member_id, flag_type=flag_type, status="open").first():
        return False
    db.add(FraudFlag(member_id=member_id, flag_type=flag_type, details=details))
    db.flush()  # autoflush is off; make the row visible to the next dedupe query
    m = db.get(Member, member_id)
    if m:
        m.is_flagged = True
    return True


def is_loopback(ip: str | None) -> bool:
    """Skip IPs we should never burst-flag: missing, loopback, or not an IP at all
    (e.g. TestClient's 'testclient' host)."""
    if not ip:
        return True
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return True


def _burst_flags(db, attr, value, label) -> list[int]:
    created = []
    members = [m for m in db.query(Member).filter(getattr(Member, attr) == value).order_by(Member.created_at)]
    for i in range(len(members)):
        window = [members[i]]
        for j in range(i + 1, len(members)):
            if (members[j].created_at or datetime.min) - (members[i].created_at or datetime.min) <= BURST_WINDOW:
                window.append(members[j])
            else:
                break
        if len(window) >= BURST_MIN:
            for m in window:
                if add_flag(db, m.id, "burst_signups",
                            f"{len(window)} sign-ups from the same {label} within 24 hours."):
                    created.append(m.id)
    return created


def _ring_flags(db) -> list[int]:
    """Cycle detection over referrer edges (A→B and B→A, or longer rings)."""
    referrer_of = {m.id: m.referrer_id for m in db.query(Member) if m.referrer_id}
    created, seen = [], set()
    for start in referrer_of:
        if start in seen:
            continue
        path, pos, cur = [], {}, start
        while cur is not None and cur in referrer_of and cur not in pos and cur not in seen:
            pos[cur] = len(path)
            path.append(cur)
            cur = referrer_of[cur]
        if cur in pos:  # cycle entirely within this walk
            cycle = path[pos[cur]:]
            ring = " → ".join(str(x) for x in cycle + cycle[:1])
            for mid in cycle:
                if add_flag(db, mid, "referral_ring", f"Referral ring detected: member ids {ring}."):
                    created.append(mid)
        seen.update(path)
    return created


def on_signup(db, m: Member, referrer: Member | None, ip: str | None, device_id: str | None) -> list[int]:
    """Checks that only make sense at signup time. Caller commits."""
    created: list[int] = []
    if referrer and referrer.id == m.id:
        if add_flag(db, m.id, "self_referral", "The referral link pointed at the member themselves."):
            created.append(m.id)
    if ip and not is_loopback(ip):
        created += _burst_flags(db, "ip", ip, "IP address")
    if device_id:
        created += _burst_flags(db, "device_id", device_id, "device")
    created += _ring_flags(db)
    return created


def scan(db) -> int:
    """Retroactive scan over all members. Returns number of new flags created."""
    created: set[int] = set()
    ips = [v for (v,) in db.query(Member.ip).filter(Member.ip.isnot(None)).distinct()]
    for ip in ips:
        if not is_loopback(ip):
            created.update(_burst_flags(db, "ip", ip, "IP address"))
    devices = [v for (v,) in db.query(Member.device_id).filter(Member.device_id.isnot(None)).distinct()]
    for dev in devices:
        created.update(_burst_flags(db, "device_id", dev, "device"))
    created.update(_ring_flags(db))
    db.commit()
    return len(created)
