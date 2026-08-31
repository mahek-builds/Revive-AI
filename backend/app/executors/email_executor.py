# app/executors/email_executor.py

def send_email(customer_id, playbook, amount, currency):
    print(
        f"Email → {customer_id} | "
        f"{playbook} | {amount} {currency}"
    )
    return "email_sent"