# app/executors/payment_executor.py

def retry_payment(customer_id, amount, currency):
    print(
        f"Payment retry → {customer_id} | "
        f"{amount} {currency}"
    )
    return "payment_retry_sent"