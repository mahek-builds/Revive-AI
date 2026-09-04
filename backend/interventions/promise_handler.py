"""
promise_handler.py — full promise-to-pay lifecycle management.
"""
import uuid
import logging
from datetime import datetime, timezone
from backend.database import get_db_connection
from backend.audit import log_event

logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    "pending":   {"fulfilled", "broken", "cancelled", "overdue"},
    "overdue":   {"fulfilled", "broken", "cancelled"},
    "fulfilled": set(),
    "broken":    set(),
    "cancelled": set(),
}


class PromiseStateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _get_promise(conn, promise_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM promise_to_pay WHERE id = ?", (promise_id,)
    ).fetchone()
    if not row:
        raise PromiseStateError("PROMISE_NOT_FOUND", f"Promise '{promise_id}' not found.")
    return dict(row)


def create_promise(
    customer_id: str,
    promised_amount: float,
    promised_date: str,
    invoice_id: str | None = None,
    payment_id: str | None = None,
    recovery_case_id: str | None = None,
    notes: str | None = None,
) -> dict:
    """Validate and create a promise-to-pay record."""
    if promised_amount <= 0:
        raise PromiseStateError("INVALID_AMOUNT", "Promised amount must be positive.")

    # Validate date is in the future
    try:
        pdate = datetime.fromisoformat(promised_date)
    except ValueError as exc:
        raise PromiseStateError("INVALID_DATE", f"promised_date is not a valid ISO-8601 date: {exc}") from exc

    if pdate.tzinfo is None:
        pdate = pdate.replace(tzinfo=timezone.utc)
    if pdate < datetime.now(timezone.utc):
        raise PromiseStateError("DATE_IN_PAST", "promised_date must be in the future.")

    # Validate customer exists
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone():
            raise PromiseStateError("CUSTOMER_NOT_FOUND", f"Customer '{customer_id}' not found.")

        promise_id = f"ppt_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO promise_to_pay
              (id, customer_id, invoice_id, payment_id, recovery_case_id,
               promised_amount, promised_date, status, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (promise_id, customer_id, invoice_id, payment_id, recovery_case_id,
             promised_amount, promised_date, notes, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("promise_to_pay", promise_id, "PROMISE_CREATED",
              f"Amount: {promised_amount}, Date: {promised_date}",
              {"customer_id": customer_id, "recovery_case_id": recovery_case_id})
    return {"promise_id": promise_id, "status": "pending"}


def _transition(promise_id: str, new_status: str, extra_fields: dict | None = None):
    conn = get_db_connection()
    try:
        promise = _get_promise(conn, promise_id)
        current = promise["status"]
        if new_status not in VALID_TRANSITIONS.get(current, set()):
            raise PromiseStateError(
                f"INVALID_TRANSITION",
                f"Cannot move promise from '{current}' to '{new_status}'.",
            )
        now = datetime.now(timezone.utc).isoformat()
        updates = {"status": new_status, "updated_at": now}
        if extra_fields:
            updates.update(extra_fields)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE promise_to_pay SET {set_clause} WHERE id = ?",
            (*updates.values(), promise_id),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("promise_to_pay", promise_id, f"PROMISE_{new_status.upper()}",
              f"Status changed: {current} → {new_status}")
    return {"promise_id": promise_id, "status": new_status}


def fulfill_promise(promise_id: str, payment_id: str) -> dict:
    """Mark promise fulfilled, validated against a real payment record."""
    conn = get_db_connection()
    try:
        payment = conn.execute(
            "SELECT id, status, amount FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if not payment:
            raise PromiseStateError("PAYMENT_NOT_FOUND", f"Payment '{payment_id}' not found.")
        if dict(payment)["status"].lower() not in ("paid", "captured", "authorized"):
            raise PromiseStateError(
                "PAYMENT_NOT_SUCCESSFUL",
                f"Payment '{payment_id}' has status '{payment['status']}' — not a successful payment.",
            )
    finally:
        conn.close()

    return _transition(promise_id, "fulfilled",
                       {"fulfilled_at": datetime.now(timezone.utc).isoformat(),
                        "payment_id": payment_id})


def break_promise(promise_id: str, reason: str = "Overdue") -> dict:
    return _transition(promise_id, "broken",
                       {"broken_at": datetime.now(timezone.utc).isoformat(),
                        "notes": reason})


def cancel_promise(promise_id: str) -> dict:
    return _transition(promise_id, "cancelled")


def check_overdue_promises() -> dict:
    """Automatically mark promises where promised_date has passed and status is still pending."""
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        rows = conn.execute(
            "SELECT id FROM promise_to_pay WHERE status = 'pending' AND promised_date < ?",
            (now_iso,),
        ).fetchall()
        updated = 0
        for row in rows:
            conn.execute(
                "UPDATE promise_to_pay SET status = 'overdue', broken_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, row["id"]),
            )
            log_event("promise_to_pay", row["id"], "PROMISE_OVERDUE",
                      "Automatically marked overdue — promised date passed")
            updated += 1
        conn.commit()
    finally:
        conn.close()
    return {"overdue_marked": updated}
