# Rule mapping error_code -> root_cause bucket
RULE_BUCKETS = {
    'BAD_REQUEST_PAYMENT_TIMED_OUT': 'bank_timeout',
    'GATEWAY_ERROR': 'gateway_downtime',
    'CARD_EXPIRED': 'card_expired',
    'INSUFFICIENT_FUNDS': 'insufficient_balance',
    'CHECKOUT_DISMISSED': 'user_abandoned',
    'INVOICE_EXPIRED': 'invoice_expired'
}

def classify_by_rules(error_code: str) -> dict:
    """Matches error_code against predefined rule buckets."""
    if error_code in RULE_BUCKETS:
        return {
            "root_cause": RULE_BUCKETS[error_code],
            "classifier_type": "rules",
            "confidence_score": 1.0,
            "reasoning": f"Exact rule match for error code '{error_code}'"
        }
    return None
