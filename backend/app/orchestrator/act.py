from app.executors.email_executor import send_email
from app.executors.sms_executor import send_sms_or_whatsapp
from app.executors.payment_executor import retry_payment
from app.executors.voice_executor import initiate_voice_call


def act(channel, customer_id, playbook, amount, currency):

    if channel == "email":
        return send_email(customer_id, playbook, amount, currency)

    elif channel in ["sms", "whatsapp"]:
        return send_sms_or_whatsapp(
            customer_id, channel, playbook, amount, currency
        )

    elif channel == "payment":
        return retry_payment(customer_id, amount, currency)

    elif channel == "voice":
        return initiate_voice_call(
            customer_id, playbook, amount, currency, "hinglish"
        )

    elif channel == "internal_task":
        print(f"Escalated case for customer {customer_id}")
        return "escalated"

    else:
        raise ValueError(f"Unknown channel: {channel}")