"""
audit.py — central audit-trail writer for reviveai.
Every meaningful state transition, AI decision, and recovery action
must be recorded through log_event().
"""
import json
import uuid
from datetime import datetime, timezone
from backend.database import get_db_connection


def log_event(
    entity_type: str,
    entity_id: str,
    action: str,
    details: str = "",
    metadata: dict | None = None,
) -> str:
    """Insert one audit log record and return its ID."""
    log_id = f"aud_{uuid.uuid4().hex[:10]}"
    meta_json = json.dumps(metadata) if metadata else None
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO audit_logs (id, entity_type, entity_id, action, details, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, entity_type, entity_id, action, details, meta_json,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return log_id
