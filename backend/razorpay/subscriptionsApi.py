from backend.razorpay.client import get_razorpay_client

def get_subscription_details(subscription_id: str) -> dict:
    """Fetches details of a subscription."""
    client = get_razorpay_client()
    return client.subscription.fetch(subscription_id)

def retry_subscription_charge(subscription_id: str) -> dict:
    """Retries recurring subscription charge."""
    client = get_razorpay_client()
    return client.subscription.fetch(subscription_id)
