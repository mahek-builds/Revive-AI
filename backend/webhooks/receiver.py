import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
processed_events = set()

def verify_webhook_signature(body_bytes: bytes, signature: str) -> bool:
    """Verifies HMAC SHA-256 signature sent by Razorpay webhook."""
    if not signature:
        return False
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

def is_duplicate_event(event_id: str) -> bool:
    """Checks if an event ID was already processed recently."""
    if not event_id:
        return False
    if event_id in processed_events:
        return True
    processed_events.add(event_id)
    return False
