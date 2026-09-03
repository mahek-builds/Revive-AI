import sqlite3
import random
import string
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "recoverai.db"
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"

def seed_test_events():
    """
    Simulates Razorpay test mode failure events:
    - Failed payments
    - Abandoned checkout
    - Halted subscriptions
    - Overdue invoices
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load and execute table schema if needed
    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
        conn.commit()

    # Create sample customer
    rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    customer_id = f"cust_{rand_str}"

    cursor.execute(
        "INSERT OR IGNORE INTO customers (id, name, email, phone) VALUES (?, ?, ?, ?)",
        (customer_id, "Razorpay Test Customer", "test.user@example.com", "+919876543210")
    )

    # 4 distinct types of simulated revenue events
    events = [
        # 1. Failed payment (Bank timeout)
        (f"rar_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}", 
         customer_id, "payment_failed", 1499.00, "INR", "pay_test101", 
         "BAD_REQUEST_PAYMENT_TIMED_OUT", "Bank server did not respond in time", "open"),

        # 2. Abandoned checkout (User closed modal)
        (f"rar_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}", 
         customer_id, "checkout_abandoned", 2999.00, "INR", "ord_test102", 
         "CHECKOUT_DISMISSED", "User closed checkout popup window", "open"),

        # 3. Halted subscription (Card expired)
        (f"rar_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}", 
         customer_id, "subscription_halted", 999.00, "INR", "sub_test103", 
         "CARD_EXPIRED", "Credit card validity expired", "open"),

        # 4. Overdue invoice (Invoice expired)
        (f"rar_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}", 
         customer_id, "invoice_overdue", 5000.00, "INR", "inv_test104", 
         "INVOICE_EXPIRED", "Payment link for invoice expired", "open"),

        # 5. High-Value Payment (Fires Stopping Rule for Manual Approval)
        (f"rar_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}", 
         customer_id, "payment_failed", 75000.00, "INR", "pay_test105", 
         "HIGH_VALUE_GATE", "High value transaction failed ($ threshold exceeded)", "open")
    ]

    cursor.executemany("""
        INSERT INTO revenue_at_risk 
        (id, customer_id, event_type, amount, currency, razorpay_entity_id, error_code, error_description, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, events)

    conn.commit()
    conn.close()
    print("Successfully seeded simulated Razorpay test events into database.")

if __name__ == "__main__":
    seed_test_events()
