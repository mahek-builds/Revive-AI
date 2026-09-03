from backend.razorpay.client import get_razorpay_client

def resend_invoice(invoice_id: str, medium: str = "email") -> dict:
    """Resends invoice notification via email/sms."""
    client = get_razorpay_client()
    return client.invoice.notify_by(invoice_id, medium)
