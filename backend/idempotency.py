"""
idempotency.py — webhook deduplication using the processed_events table.
"""
from backend.database import get_db_connection


def is_already_processed(event_id: str) -> bool:
    """Return True if this event_id has been processed before."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT event_id FROM processed_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_processed(event_id: str) -> None:
    """Record event_id so future duplicates are ignored."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)", (event_id,)
        )
        conn.commit()
    finally:
        conn.close()
