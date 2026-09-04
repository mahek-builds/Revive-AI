"""
risk_detection.py — maps raw payment/webhook events to revenue_at_risk records
and creates linked recovery cases.
"""
import uuid
import logging
from datetime import datetime, timezone
from backend.database import get_db_connection
from backend.audit import log_event

logger = logging.getLogger(__name__)

RISK_TYPE_MAP = {
    "payment.failed": "PAYMENT_FAILURE",
    "payment.error": "PAYMENT_DEGRADATION",
    "checkout.abandoned": "CHECKOUT_ABANDONMENT",
    "subscription.charged.failed": "FAILED_SUBSCRIPTION",
    "invoice.expired": "OVERDUE_INVOICE",
    "invoice.payment_failed": "PAYMENT_FAILURE",
}


def _compute_risk_score(risk_type: str, amount: float, days_overdue: int = 0) -> float:
    """Simple heuristic risk score 0–1."""
    base = {
        "PAYMENT_FAILURE": 0.70,
        "PAYMENT_DEGRADATION": 0.55,
        "CHECKOUT_ABANDONMENT": 0.40,
        "FAILED_SUBSCRIPTION": 0.75,
        "OVERDUE_INVOICE": 0.65,
        "OTHER": 0.30,
    }.get(risk_type, 0.30)
    amount_factor = min(amount / 1_000_000, 0.20)   # up to +0.20 for large amounts
    overdue_factor = min(days_overdue * 0.01, 0.10)  # up to +0.10 for very overdue
    return min(round(base + amount_factor + overdue_factor, 2), 1.0)


def detect_and_create_risk(
    event_type: str,
    customer_id: str,
    amount: float,
    currency: str = "INR",
    invoice_id: str | None = None,
    payment_id: str | None = None,
    days_overdue: int = 0,
    metadata: dict | None = None,
) -> dict:
    """
    Create a revenue_at_risk record and linked recovery_case.
    Returns a dict with rar_id and case_id.
    """
    risk_type = RISK_TYPE_MAP.get(event_type, "OTHER")
    risk_score = _compute_risk_score(risk_type, amount, days_overdue)

    now = datetime.now(timezone.utc).isoformat()
    rar_id = f"rar_{uuid.uuid4().hex[:10]}"
    case_id = f"case_{uuid.uuid4().hex[:10]}"
    priority = "HIGH" if risk_score >= 0.65 else ("MEDIUM" if risk_score >= 0.45 else "LOW")

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO revenue_at_risk
              (id, customer_id, invoice_id, payment_id, risk_type,
               amount_at_risk, risk_score, risk_status, detected_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (rar_id, customer_id, invoice_id, payment_id, risk_type,
             amount, risk_score, now, now, now),
        )
        conn.execute(
            """
            INSERT INTO recovery_cases
              (id, revenue_risk_id, customer_id, invoice_id, payment_id,
               status, priority, risk_score, amount_at_risk, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
            """,
            (case_id, rar_id, customer_id, invoice_id, payment_id,
             priority, risk_score, amount, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("revenue_at_risk", rar_id, "REVENUE_RISK_DETECTED",
              f"Risk type: {risk_type}, Amount: {amount}, Score: {risk_score}",
              metadata)
    log_event("recovery_case", case_id, "RECOVERY_CASE_CREATED",
              f"Priority: {priority}, Amount: {amount}", {"rar_id": rar_id})

    logger.info("Risk detected: rar=%s case=%s type=%s amount=%.2f", rar_id, case_id, risk_type, amount)
    return {"rar_id": rar_id, "case_id": case_id, "risk_type": risk_type, "risk_score": risk_score, "priority": priority}
