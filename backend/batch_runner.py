"""
batch_runner.py — orchestrates a full recovery batch run.
Fetches open cases, runs AI decision, applies guardrails, executes interventions.
"""
import uuid
import logging
from datetime import datetime, timezone
from backend.database import get_db_connection
from backend.recovery_case import build_case_context, transition_case, record_action_on_case, mark_recovered
from backend.ai_decision import make_recovery_decision
from backend.guardrails import enforce, GuardrailViolation
from backend.interventions.payment_link import create_payment_link
from backend.interventions.b2b_chaser import run_b2b_chaser
from backend.audit import log_event

logger = logging.getLogger(__name__)


def _execute_decision(decision, context: dict) -> dict:
    """Route the guardrail-approved decision to the right executor."""
    case_id = context["case_id"]
    customer_id = context["customer"].get("id", "")
    amount = context["amount_at_risk"]
    customer_email = context["customer"].get("email", "")
    customer_name = context["customer"].get("name", "")

    result = {}

    if decision.decision == "PAYMENT_LINK":
        result = create_payment_link(
            recovery_case_id=case_id,
            customer_id=customer_id,
            amount=amount,
            customer_email=customer_email,
            customer_name=customer_name,
        )
        transition_case(case_id, "awaiting_customer")

    elif decision.decision in ("EMAIL", "B2B_CHASER"):
        # B2B chaser runs as a standalone job — we just log the decision
        log_event("recovery_case", case_id, "ACTION_DECIDED",
                  f"B2B chaser scheduled for case {case_id}")
        transition_case(case_id, "in_progress")
        result = {"action": "B2B_CHASER", "queued": True}

    elif decision.decision == "PROMISE_TO_PAY":
        transition_case(case_id, "promise_pending")
        result = {"action": "PROMISE_TO_PAY", "note": "Awaiting customer promise creation"}

    elif decision.decision == "ESCALATION":
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE recovery_cases SET escalation_level = escalation_level + 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), case_id),
            )
            conn.commit()
        finally:
            conn.close()
        transition_case(case_id, "escalated")
        log_event("recovery_case", case_id, "ESCALATION_TRIGGERED",
                  f"Escalated by AI decision. Reason: {decision.reason}")
        result = {"action": "ESCALATION", "escalated": True}

    elif decision.decision == "STOP":
        transition_case(case_id, "stopped", stop_reason=decision.reason)
        log_event("recovery_case", case_id, "RECOVERY_STOPPED", decision.reason)
        result = {"action": "STOP", "reason": decision.reason}

    else:
        # PAYMENT_RETRY / VOICE actions — mark in_progress and log
        transition_case(case_id, "in_progress")
        result = {"action": decision.decision, "queued": True}

    record_action_on_case(case_id, decision.decision)
    return result


def run_batch() -> dict:
    """
    Full batch recovery run:
    1. Fetch all open/analyzing/action_pending recovery cases
    2. For each: build context → AI decision → guardrail → execute
    3. Record batch run metrics in batch_runs table
    4. Return summary dict
    """
    batch_id = f"batch_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO batch_runs (id, status, started_at) VALUES (?, 'running', ?)",
            (batch_id, now),
        )
        conn.commit()
        cases = conn.execute(
            """
            SELECT id, amount_at_risk FROM recovery_cases
            WHERE status IN ('open', 'analyzing', 'action_pending', 'in_progress')
            ORDER BY risk_score DESC, created_at ASC
            LIMIT 100
            """
        ).fetchall()
    finally:
        conn.close()

    total_amount_at_risk = sum(float(c["amount_at_risk"] or 0) for c in cases)
    actions_executed = 0
    errors = 0

    log_event("batch", batch_id, "BATCH_STARTED",
              f"Processing {len(cases)} cases, ₹{total_amount_at_risk:,.2f} at risk")

    for case_row in cases:
        case_id = case_row["id"]
        try:
            context = build_case_context(case_id)
            if not context:
                continue

            # Move to analyzing
            try:
                transition_case(case_id, "analyzing")
            except ValueError:
                pass  # Already in a different state, continue

            log_event("recovery_case", case_id, "AI_DECISION_STARTED",
                      f"Batch {batch_id}: requesting AI decision")

            decision = make_recovery_decision(context)
            log_event("recovery_case", case_id, "AI_DECISION_MADE",
                      f"Decision: {decision.decision}, Priority: {decision.priority}. {decision.reason}",
                      {"batch_id": batch_id, "decision": decision.model_dump()})

            approved_decision = enforce(decision, context)
            log_event("recovery_case", case_id, "ACTION_APPROVED",
                      f"Guardrail passed for {approved_decision.decision}")

            result = _execute_decision(approved_decision, context)
            actions_executed += 1
            log_event("recovery_case", case_id, "ACTION_EXECUTED",
                      str(result), {"batch_id": batch_id})

        except GuardrailViolation as gv:
            log_event("recovery_case", case_id, "ACTION_REJECTED",
                      f"Guardrail: {gv.code} — {gv.message}")
            logger.warning("Guardrail blocked %s: %s", case_id, gv.message)
        except Exception as exc:
            logger.error("Error processing case %s: %s", case_id, exc, exc_info=True)
            log_event("recovery_case", case_id, "BATCH_ERROR", str(exc)[:500])
            errors += 1

    # Complete batch
    done = datetime.now(timezone.utc).isoformat()
    conn2 = get_db_connection()
    try:
        # Recalculate recovered amount for this batch
        amount_recovered = conn2.execute(
            "SELECT COALESCE(SUM(amount_recovered), 0) as tot FROM recovery_cases WHERE status = 'recovered'"
        ).fetchone()["tot"]

        conn2.execute(
            """
            UPDATE batch_runs SET status='completed', cases_processed=?, actions_executed=?,
              amount_at_risk=?, amount_recovered=?, completed_at=?
            WHERE id=?
            """,
            (len(cases), actions_executed, total_amount_at_risk, float(amount_recovered), done, batch_id),
        )
        conn2.commit()
    finally:
        conn2.close()

    log_event("batch", batch_id, "BATCH_COMPLETED",
              f"Processed {len(cases)} cases, {actions_executed} actions, {errors} errors")

    return {
        "batch_id": batch_id,
        "cases_processed": len(cases),
        "actions_executed": actions_executed,
        "errors": errors,
        "amount_at_risk": total_amount_at_risk,
        "status": "completed",
    }


def get_batch(batch_id: str) -> dict | None:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM batch_runs WHERE id = ?", (batch_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
