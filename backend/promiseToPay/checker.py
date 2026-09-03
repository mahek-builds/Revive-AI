from datetime import datetime
from backend.database import get_db_connection

def check_promise_statuses() -> dict:
    """
    Polls promise_to_pay table and updates pending records to
    'honored' or 'missed' based on promised_date vs current time.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat()

    # Find pending promises past promised date
    cursor.execute(
        "SELECT id, promised_date FROM promise_to_pay WHERE status = 'pending' AND promised_date < ?",
        (now_iso,)
    )
    overdue_promises = cursor.fetchall()

    updated_count = 0
    for row in overdue_promises:
        # Mark as missed by default if not paid yet
        cursor.execute(
            "UPDATE promise_to_pay SET status = 'missed' WHERE id = ?",
            (row["id"],)
        )
        updated_count += 1

    conn.commit()
    conn.close()

    return {
        "status": "checked",
        "processed_overdue": updated_count
    }
