import random
import string

def parse_webhook_payload(payload: dict) -> dict:
    """
    Converts raw Razorpay webhook payload into a revenue_at_risk database record dict.
    Supports events across Payment, Order, Invoice, Payment Link, and Subscription entities.
    """
    event_type = payload.get("event", "")
    payload_body = payload.get("payload", {})

    # Extract primary entity object from payload (payment / order / invoice / payment_link / subscription)
    entity = {}
    if "payment" in payload_body:
        entity = payload_body["payment"].get("entity", {})
    elif "order" in payload_body:
        entity = payload_body["order"].get("entity", {})
    elif "invoice" in payload_body:
        entity = payload_body["invoice"].get("entity", {})
    elif "payment_link" in payload_body:
        entity = payload_body["payment_link"].get("entity", {})
    elif "subscription" in payload_body:
        entity = payload_body["subscription"].get("entity", {})

    # Extract monetary amount in rupees
    amount_paise = entity.get("amount") or entity.get("amount_paid") or 0
    amount_rupees = float(amount_paise) / 100.0 if amount_paise else 0.0

    currency = entity.get("currency", "INR")
    razorpay_id = entity.get("id") or payload.get("account_id") or ""
    error_code = entity.get("error_code") or "UNKNOWN_ERROR"
    error_desc = entity.get("error_description") or f"Razorpay event: {event_type}"
    customer_id = entity.get("customer_id") or entity.get("customer", {}).get("id") or "cust_unknown"

    # Determine status: recovered vs open
    status = "open"
    if event_type in ["payment.captured", "payment_link.paid", "invoice.paid", "order.paid"]:
        status = "recovered"

    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    return {
        "id": f"rar_{rand_suffix}",
        "customer_id": customer_id,
        "event_type": event_type,
        "amount": amount_rupees,
        "currency": currency,
        "razorpay_entity_id": razorpay_id,
        "error_code": error_code,
        "error_description": error_desc,
        "status": status
    }
