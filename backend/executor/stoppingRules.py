def should_stop_intervention(attempts: int, amount: float, is_opted_out: bool = False) -> dict:
    """
    Evaluates stopping rules:
    - Max 3 recovery attempts limit
    - INR 50,000 threshold requiring manual high-value review
    - Customer opt-out check
    """
    if is_opted_out:
        return {"stop": True, "reason": "Customer opted out of automated communications"}
    if attempts >= 3:
        return {"stop": True, "reason": "Exceeded max recovery attempts limit (3)"}
    if amount > 50000.0:
        return {"stop": True, "reason": "Amount exceeds manual review threshold (INR 50,000)"}
    return {"stop": False, "reason": ""}
