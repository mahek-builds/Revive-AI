from datetime import datetime, timezone
from app.config import *
from app.models import Suppression


def _as_utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def check_guardrails(db, case):
    now = datetime.now(timezone.utc)

    attempt_ok = case.attempts < MAX_ATTEMPTS_PER_CASE

    cooldown_ok = (
        case.last_action_at is None or
        (now - _as_utc(case.last_action_at)).total_seconds()
        >= COOLDOWN_HOURS_SAME_CASE * 3600
    )

    quiet_ok = (
        DEMO_MODE or
        not (now.hour >= QUIET_HOURS_START or now.hour < QUIET_HOURS_END)
    )

    suppressed = db.query(Suppression).filter(
        Suppression.customer_id == case.customer_id
    ).first()

    not_suppressed = suppressed is None

    lifetime_ok = (
        now - _as_utc(case.created_at)
    ).total_seconds() <= CASE_AUTO_CLOSE_DAYS * 86400

    return {
        "attempt_cap_ok": attempt_ok,
        "cooldown_ok": cooldown_ok,
        "quiet_hours_ok": quiet_ok,
        "not_suppressed": not_suppressed,
        "within_case_lifetime": lifetime_ok,
        "all_passed": all([
            attempt_ok,
            cooldown_ok,
            quiet_ok,
            not_suppressed,
            lifetime_ok
        ])
    }