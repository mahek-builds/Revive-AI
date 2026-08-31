from app.models import RecoveryCase
from app.orchestrator.state_machine import run_cycle


def process_open_cases(db):
    cases = db.query(RecoveryCase).filter(
        RecoveryCase.status == "open"
    ).all()

    for case in cases:
        # yahan raw reason ka source abhi model mein directly nahi hai
        run_cycle(db, case, ???)