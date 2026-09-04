"""
recovery_case.py — recovery case state machine, context loader, and lifecycle management.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from backend.database import get_db_connection
from backend.audit import log_event
from backend.config import MIN_HOURS_BETWEEN_CONTACTS

logger = logging.getLogger(__name__)

VALID_STATUSES = {
    "open", "analyzing", "action_pending", "in_progress",
    "awaiting_customer", "promise_pending", "escalated",
    "recovered", "disputed", "stopped", "failed",
}

VALID_TRANSITIONS = {
    "open":              {"analyzing", "action_pending", "stopped", "failed"},
    "analyzing":         {"action_pending", "stopped", "failed"},
    "action_pending":    {"in_progress", "awaiting_customer", "escalated", "stopped", "failed"},
    "in_progress":       {"awaiting_customer", "promise_pending", "recovered", "escalated", "stopped", "failed"},
    "awaiting_customer": {"in_progress", "promise_pending", "recovered", "disputed", "escalated", "stopped", "failed"},
    "promise_pending":   {"recovered", "in_progress", "disputed", "escalated", "stopped", "failed"},
    "escalated":         {"in_progress", "recovered", "disputed", "stopped", "failed"},
    "recovered":         set(),
    "disputed":          {"stopped", "failed"},
    "stopped":           set(),
    "failed":            set(),
}


def get_case(case_id: str) -> dict | None:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM recovery_cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def transition_case(case_id: str, new_status: str, stop_reason: str | None = None) -> dict:
    """Transition a recovery case to a new status, enforcing the state machine."""
    case = get_case(case_id)
    if not case:
        raise ValueError(f"Recovery case '{case_id}' not found.")
    current = case["status"]
    if new_status not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: '{current}' → '{new_status}'")

    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        updates = f"status = ?, updated_at = ?"
        params = [new_status, now]
        if stop_reason:
            updates += ", stop_reason = ?"
            params.append(stop_reason)
        params.append(case_id)
        conn.execute(f"UPDATE recovery_cases SET {updates} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()

    log_event("recovery_case", case_id, "CASE_STATUS_CHANGED",
              f"{current} → {new_status}",
              {"stop_reason": stop_reason} if stop_reason else None)
    return {"case_id": case_id, "previous_status": current, "new_status": new_status}


def record_action_on_case(case_id: str, action: str) -> None:
    """Increment attempt_count, set last_action, and schedule next_action_at."""
    now = datetime.now(timezone.utc)
    next_contact = (now + timedelta(hours=MIN_HOURS_BETWEEN_CONTACTS)).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE recovery_cases
            SET attempt_count = attempt_count + 1,
                last_action = ?,
                next_action_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (action, next_contact, now.isoformat(), case_id),
        )
        conn.commit()
    finally:
        conn.close()


def build_case_context(case_id: str) -> dict:
    """Load full context needed by the AI decision agent."""
    conn = get_db_connection()
    try:
        case = conn.execute("SELECT * FROM recovery_cases WHERE id = ?", (case_id,)).fetchone()
        if not case:
            return {}
        case = dict(case)

        customer = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (case["customer_id"],)
        ).fetchone()

        invoice = None
        if case.get("invoice_id"):
            invoice = conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (case["invoice_id"],)
            ).fetchone()

        payment = None
        if case.get("payment_id"):
            payment = conn.execute(
                "SELECT * FROM payments WHERE id = ?", (case["payment_id"],)
            ).fetchone()

        previous_actions = conn.execute(
            "SELECT action_type, status, executed_at FROM recovery_actions WHERE recovery_case_id = ? ORDER BY executed_at DESC LIMIT 10",
            (case_id,),
        ).fetchall()

        promises = conn.execute(
            "SELECT id, promised_amount, promised_date, status FROM promise_to_pay WHERE recovery_case_id = ?",
            (case_id,),
        ).fetchall()

    finally:
        conn.close()

    # Compute days overdue
    days_overdue = 0
    if invoice and invoice["due_date"]:
        try:
            due = datetime.fromisoformat(invoice["due_date"])
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            days_overdue = max(0, (datetime.now(timezone.utc) - due).days)
        except ValueError:
            pass

    return {
        "case_id": case_id,
        "status": case["status"],
        "priority": case["priority"],
        "risk_score": case["risk_score"],
        "amount_at_risk": case["amount_at_risk"],
        "amount_recovered": case["amount_recovered"],
        "attempt_count": case["attempt_count"],
        "max_attempts": case["max_attempts"],
        "escalation_level": case["escalation_level"],
        "max_escalation_level": case["max_escalation_level"],
        "last_action": case["last_action"],
        "next_action_at": case["next_action_at"],
        "created_at": case["created_at"],
        "customer": dict(customer) if customer else {},
        "invoice": dict(invoice) if invoice else {},
        "payment": dict(payment) if payment else {},
        "days_overdue": days_overdue,
        "previous_actions": [dict(a) for a in previous_actions],
        "promises": [dict(p) for p in promises],
    }


def mark_recovered(case_id: str, recovered_amount: float, payment_id: str) -> dict:
    """Mark case as recovered with actual payment-backed amount."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE recovery_cases
            SET status = 'recovered', amount_recovered = ?, stop_reason = 'PAYMENT_RECEIVED',
                updated_at = ?
            WHERE id = ?
            """,
            (recovered_amount, now, case_id),
        )
        # Also update the linked revenue_at_risk record
        case = conn.execute("SELECT revenue_risk_id FROM recovery_cases WHERE id = ?", (case_id,)).fetchone()
        if case and case["revenue_risk_id"]:
            conn.execute(
                "UPDATE revenue_at_risk SET risk_status = 'resolved', resolved_at = ?, resolution_reason = 'PAYMENT_RECEIVED', updated_at = ? WHERE id = ?",
                (now, now, case["revenue_risk_id"]),
            )
        conn.commit()
    finally:
        conn.close()

    log_event("recovery_case", case_id, "RECOVERY_COMPLETED",
              f"Recovered ₹{recovered_amount:,.2f} via payment {payment_id}",
              {"payment_id": payment_id, "amount_recovered": recovered_amount})
    return {"case_id": case_id, "status": "recovered", "amount_recovered": recovered_amount}
