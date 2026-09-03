# Decision matrix mapping root_cause -> action, channel, delay_minutes
DECISION_MATRIX = {
    'bank_timeout': {'action': 'retry_charge', 'channel': 'system', 'delay_minutes': 60},
    'gateway_downtime': {'action': 'retry_charge', 'channel': 'system', 'delay_minutes': 120},
    'card_expired': {'action': 'card_update_prompt', 'channel': 'email', 'delay_minutes': 0},
    'insufficient_balance': {'action': 'send_payment_link', 'channel': 'whatsapp', 'delay_minutes': 1440},
    'user_abandoned': {'action': 'send_payment_link', 'channel': 'whatsapp', 'delay_minutes': 15},
    'invoice_expired': {'action': 'resend_invoice', 'channel': 'email', 'delay_minutes': 0}
}

def decide_action_for_cause(root_cause: str) -> dict:
    """Returns recommended recovery action, communication channel, and delay interval."""
    return DECISION_MATRIX.get(root_cause, {
        'action': 'send_payment_link',
        'channel': 'email',
        'delay_minutes': 30
    })
