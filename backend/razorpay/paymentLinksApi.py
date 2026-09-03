from backend.razorpay.client import get_razorpay_client

def create_payment_link(amount: float, currency: str = "INR", description: str = "Revenue Recovery", customer: dict = None) -> dict:
    """Creates a new Razorpay Payment Link."""
    client = get_razorpay_client()
    payload = {
        "amount": int(round(amount * 100)),
        "currency": currency or "INR",
        "description": description,
        "notify": {"sms": True, "email": True}
    }
    if customer:
        payload["customer"] = customer
    return client.payment_link.create(payload)
