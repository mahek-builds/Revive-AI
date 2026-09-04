def get_escalation_tier(days_overdue: int) -> dict:
    """
    Escalation ladder logic:
    - Day 0-3: Gentle automated retry / soft reminder
    - Day 4-14: Urgent payment link via WhatsApp/Email
    - Day 15-30: Discount offer or flexible promise-to-pay option
    - Day 30+: Manual agent outreach / write-off review
    """
    if days_overdue <= 3:
        return {
            "tier": "soft_nudge",
            "recommended_tone": "friendly",
            "allow_automated_retry": True
        }
    elif days_overdue <= 14:
        return {
            "tier": "urgent_reminder",
            "recommended_tone": "direct",
            "allow_automated_retry": True
        }
    elif days_overdue <= 30:
        return {
            "tier": "incentivized_recovery",
            "recommended_tone": "empathetic",
            "offer_discount": True
        }
    else:
        return {
            "tier": "manual_escalation",
            "recommended_tone": "firm",
            "requires_human_agent": True
        }
