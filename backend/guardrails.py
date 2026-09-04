"""
guardrails.py — deterministic rule engine that sits between the LLM decision
and action execution.  The LLM cannot override these rules.
"""
import logging
from datetime import datetime, timezone, timedelta
from backend.config import MAX_ATTEMPTS, MAX_ESCALATION_LEVEL, RECOVERY_WINDOW_DAYS, MIN_HOURS_BETWEEN_CONTACTS
from backend.ai_decision import Decision

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"recovered", "stopped", "failed", "disputed"}
STOP_ACTIONS = {"STOP"}


class GuardrailViolation(Exception):
    """Raised when the guardrail engine rejects the AI decision."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def enforce(decision: Decision, case: dict) -> Decision:
    """
    Validate the LLM decision against deterministic business rules.
    Returns the decision if allowed; raises GuardrailViolation if rejected.
    The case dict must include:
      status, attempt_count, max_attempts, escalation_level, max_escalation_level,
      last_action (optional), next_action_at (optional), created_at.
    """
    status = (case.get("status") or "").lower()

    # 1. Never act on terminal cases
    if status in TERMINAL_STATUSES:
        raise GuardrailViolation(
            "CASE_TERMINAL",
            f"Recovery case is already in terminal state '{status}'. No further actions allowed.",
        )

    # 2. Max attempts
    attempt_count = int(case.get("attempt_count") or 0)
    max_attempts = int(case.get("max_attempts") or MAX_ATTEMPTS)
    if attempt_count >= max_attempts and decision.decision not in STOP_ACTIONS:
        raise GuardrailViolation(
            "MAX_ATTEMPTS_REACHED",
            f"Case has reached maximum attempts ({max_attempts}). Action blocked — use STOP.",
        )

    # 3. Max escalation
    escalation_level = int(case.get("escalation_level") or 0)
    max_esc = int(case.get("max_escalation_level") or MAX_ESCALATION_LEVEL)
    if decision.requires_escalation and escalation_level >= max_esc:
        raise GuardrailViolation(
            "MAX_ESCALATION_REACHED",
            f"Escalation level {escalation_level} is already at maximum ({max_esc}). Escalation blocked.",
        )

    # 4. Contact frequency — minimum hours between outreach actions
    OUTREACH_ACTIONS = {"EMAIL", "B2B_CHASER", "VOICE_CALL", "HINGLISH_VOICE", "PAYMENT_LINK"}
    if decision.decision in OUTREACH_ACTIONS:
        next_action_at_str = case.get("next_action_at")
        if next_action_at_str:
            try:
                next_dt = datetime.fromisoformat(next_action_at_str)
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < next_dt:
                    raise GuardrailViolation(
                        "CONTACT_TOO_SOON",
                        f"Minimum {MIN_HOURS_BETWEEN_CONTACTS}h between contacts not elapsed. Next allowed: {next_action_at_str}.",
                    )
            except ValueError:
                pass   # unparseable date → allow

    # 5. Recovery window
    created_at_str = case.get("created_at")
    if created_at_str:
        try:
            created = datetime.fromisoformat(created_at_str)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            window_end = created + timedelta(days=RECOVERY_WINDOW_DAYS)
            if datetime.now(timezone.utc) > window_end and decision.decision not in STOP_ACTIONS:
                raise GuardrailViolation(
                    "RECOVERY_WINDOW_EXPIRED",
                    f"Recovery window of {RECOVERY_WINDOW_DAYS} days has expired. Use STOP.",
                )
        except ValueError:
            pass

    logger.info("Guardrail passed for decision=%s case_id=%s", decision.decision, case.get("id"))
    return decision
