# app/orchestrator/verify.py

import random


def verify_outcome(case_id):
    outcome = random.random()

    if outcome < 0.45:
        return "recovered"

    elif outcome < 0.70:
        return "pending"

    else:
        return "failed"