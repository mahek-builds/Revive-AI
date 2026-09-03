import os
import razorpay
from dotenv import load_dotenv

load_dotenv()

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

def get_razorpay_client():
    """Initializes and returns thin Razorpay SDK client."""
    return razorpay.Client(auth=(KEY_ID, KEY_SECRET))
