"""
b2b_chaser.py — B2B overdue invoice recovery using real DB records and Groq LLM.
"""
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from backend.config import LLM_API_KEY, LLM_MODEL, MIN_HOURS_BETWEEN_CONTACTS
from backend.database import get_db_connection
from backend.audit import log_event
from groq import Groq

logger = logging.getLogger(__name__)
_client = Groq(api_key=LLM_API_KEY)


def _generate_chaser_message(context: dict) -> str:
    """Use Groq to write a personalised collection email."""
    prompt = f"""
Write a professional, polite but firm payment-chaser email for this overdue invoice.
Return ONLY the plain text email body (no Subject line, no JSON).

Context:
{json.dumps(context, indent=2)}
"""
    try:
        resp = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Groq failed to generate chaser email: {exc}") from exc


def run_b2b_chaser(max_cases: int = 50) -> dict:
    """
    Scan overdue invoices from the real DB, generate personalised chasers,
    record recovery_actions, and return a summary.
    """
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    overdue_threshold = datetime.now(timezone.utc).isoformat()

    try:
        # Find invoices where due_date has passed and status is not paid
        rows = conn.execute(
            """
            SELECT i.id as invoice_id, i.external_invoice_id, i.amount, i.due_date,
                   i.customer_id, i.currency, i.created_at as invoice_created,
                   c.name as customer_name, c.email as customer_email,
                   c.company_name,
                   rc.id as case_id, rc.attempt_count, rc.escalation_level,
                   rc.next_action_at
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            LEFT JOIN recovery_cases rc ON rc.invoice_id = i.id AND rc.status NOT IN ('recovered','stopped','failed')
            WHERE i.status != 'paid'
              AND i.due_date < ?
            ORDER BY i.due_date ASC
            LIMIT ?
            """,
            (overdue_threshold, max_cases),
        ).fetchall()
    finally:
        conn.close()

    created = 0
    skipped = 0

    for row in rows:
        # Respect contact frequency
        if row["next_action_at"]:
            try:
                next_dt = datetime.fromisoformat(row["next_action_at"])
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < next_dt:
                    skipped += 1
                    continue
            except ValueError:
                pass

        days_overdue = 0
        if row["due_date"]:
            try:
                due = datetime.fromisoformat(row["due_date"])
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
                days_overdue = max(0, (datetime.now(timezone.utc) - due).days)
            except ValueError:
                pass

        context = {
            "company_name": row["company_name"] or "Valued Customer",
            "customer_name": row["customer_name"] or "Sir/Ma'am",
            "invoice_id": row["external_invoice_id"] or row["invoice_id"],
            "amount": row["amount"],
            "currency": row["currency"] or "INR",
            "days_overdue": days_overdue,
            "previous_attempts": row["attempt_count"] or 0,
        }

        try:
            email_body = _generate_chaser_message(context)
        except RuntimeError as exc:
            logger.error("Failed to generate chaser for invoice %s: %s", row["invoice_id"], exc)
            skipped += 1
            continue

        action_id = f"act_{uuid.uuid4().hex[:10]}"
        next_contact = (datetime.now(timezone.utc) + timedelta(hours=MIN_HOURS_BETWEEN_CONTACTS)).isoformat()

        conn2 = get_db_connection()
        try:
            # Upsert a recovery case if none exists
            case_id = row["case_id"]
            if not case_id:
                case_id = f"case_{uuid.uuid4().hex[:10]}"
                conn2.execute(
                    """
                    INSERT INTO recovery_cases
                      (id, customer_id, invoice_id, status, priority, amount_at_risk, created_at, updated_at)
                    VALUES (?, ?, ?, 'open', 'MEDIUM', ?, ?, ?)
                    """,
                    (case_id, row["customer_id"], row["invoice_id"], row["amount"], now_iso, now_iso),
                )

            conn2.execute(
                """
                INSERT INTO recovery_actions
                  (id, recovery_case_id, customer_id, action_type, channel,
                   status, reason, attempt_number, executed_at)
                VALUES (?, ?, ?, 'B2B_CHASER', 'email', 'executed', ?, ?, ?)
                """,
                (action_id, case_id, row["customer_id"], email_body[:1000],
                 (row["attempt_count"] or 0) + 1, now_iso),
            )
            # Update case attempt count and next contact window
            conn2.execute(
                """
                UPDATE recovery_cases
                SET attempt_count = attempt_count + 1,
                    last_action = 'B2B_CHASER',
                    next_action_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (next_contact, now_iso, case_id),
            )
            conn2.commit()
        finally:
            conn2.close()

        log_event("recovery_action", action_id, "B2B_CHASER_SENT",
                  f"Invoice {row['invoice_id']} — {days_overdue}d overdue",
                  {"case_id": case_id, "email_body_preview": email_body[:200]})
        created += 1

    return {"chasers_sent": created, "skipped": skipped}
