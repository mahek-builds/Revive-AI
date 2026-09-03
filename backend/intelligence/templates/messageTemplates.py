# Pre-approved template library for notifications (No freeform LLM generated message text allowed)

MESSAGE_TEMPLATES = {
    "card_expired_email": {
        "subject": "Action Required: Update your payment card details",
        "body": "Hi {customer_name}, your card ending in {card_last4} has expired. Please update your details to continue your subscription."
    },
    "payment_link_whatsapp": {
        "body": "Hi {customer_name}, your recent payment of ₹{amount} for {product_name} was unsuccessful. Click here to safely complete payment: {payment_url}"
    },
    "bank_timeout_system": {
        "body": "System auto-retrying charge for transaction {transaction_id} due to bank timeout."
    },
    "invoice_reminder_email": {
        "subject": "Invoice Reminder for {invoice_id}",
        "body": "Hi {customer_name}, your invoice #{invoice_id} for ₹{amount} is pending. Please complete payment using this link: {payment_url}"
    }
}

def get_formatted_template(template_key: str, variables: dict) -> str:
    """Retrieves a pre-approved message template formatted with safe variables."""
    template = MESSAGE_TEMPLATES.get(template_key)
    if not template:
        return "Standard payment reminder from RecoverAI."

    text = template.get("body", "")
    for key, value in variables.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text
