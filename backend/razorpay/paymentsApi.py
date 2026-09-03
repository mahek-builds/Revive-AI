from backend.razorpay.client import get_razorpay_client

def get_payment_by_id(payment_id: str) -> dict:
    """Fetches single payment by payment_id."""
    client = get_razorpay_client()
    return client.payment.fetch(payment_id)

def get_order_payments(order_id: str) -> list:
    """Fetches all payments associated with an order_id."""
    client = get_razorpay_client()
    return client.order.payments(order_id)
