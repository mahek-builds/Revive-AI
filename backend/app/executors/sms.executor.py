# app/executors/sms_executor.py

def send_sms_or_whatsapp(
    customer_id,
    channel,
    playbook,
    amount,
    currency
):
    print(
        f"{channel.upper()} → {customer_id} | "
        f"{playbook} | {amount} {currency}"
    )
    return f"{channel}_sent"