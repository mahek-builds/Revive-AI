"""
payment_link.py — creates a real Razorpay payment link (test mode) for recovery.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from backend.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from backend.database import get_db_connection
from backend.audit import log_event
import razorpay

logger = logging.getLogger(__name__)
_rzp = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_payment_link(
    recovery_case_id: str,
    customer_id: str,
    amount: float,
    customer_email: str = "",
    customer_name: str = "",
    customer_contact: str = "",
    description: str = "Recovery payment",
) -> dict:
    """
    Create a Razorpay payment link in test mode.
    Stores the result as a recovery_action record.
    Returns the Razorpay response dict.
    """
    amount_paise = int(amount * 100)
    expire_by = int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp())

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "description": description,
        "expire_by": expire_by,
        "notify": {"sms": False, "email": bool(customer_email)},
        "reminder_enable": False,
    }
    if customer_name or customer_email or customer_contact:
        payload["customer"] = {}
        if customer_name:
            payload["customer"]["name"] = customer_name
        if customer_email:
            payload["customer"]["email"] = customer_email
        if customer_contact:
            payload["customer"]["contact"] = customer_contact

    try:
        rzp_response = _rzp.payment_link.create(payload)
    except Exception as exc:
        raise RuntimeError(f"Razorpay payment_link.create failed: {exc}") from exc

    action_id = f"act_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO recovery_actions
              (id, recovery_case_id, customer_id, action_type, channel,
               status, external_reference, executed_at)
            VALUES (?, ?, ?, 'PAYMENT_LINK', 'razorpay', 'executed', ?, ?)
            """,
            (action_id, recovery_case_id, customer_id, rzp_response.get("id"), now),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("recovery_action", action_id, "PAYMENT_LINK_CREATED",
              f"Razorpay link ID: {rzp_response.get('id')}, URL: {rzp_response.get('short_url')}",
              {"case_id": recovery_case_id, "amount": amount})

    logger.info("Payment link created: %s", rzp_response.get("short_url"))
    return {"action_id": action_id, "razorpay_link_id": rzp_response.get("id"),
            "short_url": rzp_response.get("short_url"), "status": "created"}
