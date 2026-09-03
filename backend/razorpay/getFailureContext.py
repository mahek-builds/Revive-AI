def get_failure_context(error_code: str, error_description: str = "") -> dict:
    """
    Shared interface used by intelligence diagnosis module to gather
    failure context details from Razorpay event fields.
    """
    return {
        "error_code": error_code,
        "error_description": error_description or "No error description provided",
        "has_error_code": bool(error_code)
    }
