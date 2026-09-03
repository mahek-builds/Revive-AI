import time

def calculate_backoff_seconds(attempt: int, base_seconds: int = 2) -> int:
    """Calculates exponential backoff delay in seconds for API retries (429 Rate Limits)."""
    return base_seconds * (2 ** (attempt - 1))

def wait_with_backoff(attempt: int, base_seconds: int = 2):
    """Pauses thread execution using exponential backoff."""
    delay = calculate_backoff_seconds(attempt, base_seconds)
    time.sleep(delay)
