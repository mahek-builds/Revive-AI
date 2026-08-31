# app/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RecoveryCase, RecoveryAction

router = APIRouter(prefix="/api")


# 1. Get all cases
@router.get("/cases")
def get_cases(db: Session = Depends(get_db)):
    return db.query(RecoveryCase).all()


# 2. Get audit/history of a case
@router.get("/cases/{case_id}/audit")
def get_case_audit(case_id: int, db: Session = Depends(get_db)):

    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id
    ).first()

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    actions = db.query(RecoveryAction).filter(
        RecoveryAction.case_id == case_id
    ).all()

    return actions


# 3. Promise to pay
@router.post("/cases/{case_id}/promise-to-pay")
def promise_to_pay(
    case_id: int,
    db: Session = Depends(get_db)
):
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id
    ).first()

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    # TODO:
    # promised payment date save karne ke liye
    # RecoveryCase model mein field add karni hogi.

    return {
        "message": "Promise-to-pay endpoint reached",
        "case_id": case_id
    }


# 4. Metrics
@router.get("/metrics/summary")
def metrics_summary(db: Session = Depends(get_db)):

    total_cases = db.query(RecoveryCase).count()

    recovered_cases = db.query(RecoveryCase).filter(
        RecoveryCase.status == "recovered"
    ).count()

    escalated_cases = db.query(RecoveryCase).filter(
        RecoveryCase.status == "escalated"
    ).count()

    recovery_rate = (
        recovered_cases / total_cases * 100
        if total_cases > 0
        else 0
    )

    return {
        "total_cases": total_cases,
        "recovered_cases": recovered_cases,
        "escalated_cases": escalated_cases,
        "recovery_rate_pct": recovery_rate
    }