"""
routes_v2.py — all Track 03 API routes mounted under /api/v2/
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field

from backend.auth import require_api_key
from backend.audit import log_event as _audit
from backend.database import get_db_connection
from backend.risk_detection import detect_and_create_risk
from backend.recovery_case import get_case, build_case_context, mark_recovered
from backend.ai_decision import make_recovery_decision
from backend.guardrails import enforce as guardrail_enforce, GuardrailViolation
from backend.interventions.payment_link import create_payment_link as _create_plink
from backend.interventions.b2b_chaser import run_b2b_chaser as _run_b2b
from backend.interventions.voice_recovery import process_voice_audio
from backend.interventions.promise_handler import (
    create_promise, fulfill_promise, break_promise, cancel_promise,
    check_overdue_promises, PromiseStateError,
)
from backend.recovery_metrics import compute_recovery_metrics
from backend.batch_runner import run_batch as _run_batch, get_batch as _get_batch

router = APIRouter(prefix="/api/v2", tags=["Track 03"])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class CreateCustomerRequest(BaseModel):
    name: str = Field(..., max_length=120)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=20)
    company_name: str = Field(default="", max_length=200)
    customer_type: str = Field(default="individual", max_length=50)
    external_customer_id: str = Field(default="", max_length=100)


class CreateInvoiceRequest(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    external_invoice_id: str = Field(default="")
    status: str = Field(default="unpaid")
    due_date: str = Field(...)


class CreatePaymentRequest(BaseModel):
    customer_id: str
    invoice_id: str = Field(default="")
    external_payment_id: str = Field(default="")
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    status: str = Field(default="captured")
    failure_reason: str = Field(default="")
    payment_method: str = Field(default="")


class CreatePromiseRequest(BaseModel):
    customer_id: str
    invoice_id: Optional[str] = None
    payment_id: Optional[str] = None
    recovery_case_id: Optional[str] = None
    promised_amount: float = Field(gt=0)
    promised_date: str
    notes: Optional[str] = None


class FulfillPromiseRequest(BaseModel):
    payment_id: str


class CreateRiskEventRequest(BaseModel):
    event_type: str = Field(default="payment.failed")
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = Field(default="INR")
    invoice_id: Optional[str] = None
    payment_id: Optional[str] = None
    days_overdue: int = Field(default=0, ge=0)


# ─── Customers ───────────────────────────────────────────────────────────────

@router.post("/customers", dependencies=[Depends(require_api_key)])
def create_customer(req: CreateCustomerRequest):
    """Create a real customer record."""
    cust_id = f"cust_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO customers
              (id, external_customer_id, name, email, phone, company_name, customer_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cust_id, req.external_customer_id, req.name, req.email, req.phone,
             req.company_name, req.customer_type, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    _audit("customer", cust_id, "CUSTOMER_CREATED", req.name)
    return {"customer_id": cust_id, "name": req.name}


@router.get("/customers", dependencies=[Depends(require_api_key)])
def list_customers(limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM customers ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── Invoices ────────────────────────────────────────────────────────────────

@router.post("/invoices", dependencies=[Depends(require_api_key)])
def create_invoice(req: CreateInvoiceRequest):
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT id FROM customers WHERE id = ?", (req.customer_id,)).fetchone():
            raise HTTPException(status_code=404, detail={"error": {"code": "CUSTOMER_NOT_FOUND", "message": f"Customer {req.customer_id} not found."}})
        inv_id = f"inv_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO invoices (id, external_invoice_id, customer_id, amount, currency, status, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inv_id, req.external_invoice_id, req.customer_id, req.amount, req.currency, req.status, req.due_date, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"invoice_id": inv_id}


@router.get("/invoices", dependencies=[Depends(require_api_key)])
def list_invoices(customer_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM invoices WHERE 1=1"
        p: list = []
        if customer_id:
            q += " AND customer_id = ?"; p.append(customer_id)
        if status:
            q += " AND status = ?"; p.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── Payments ────────────────────────────────────────────────────────────────

@router.post("/payments", dependencies=[Depends(require_api_key)])
def record_payment(req: CreatePaymentRequest):
    """Record an actual payment. Triggers recovery reconciliation if successful."""
    pay_id = f"pay_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO payments (id, external_payment_id, customer_id, invoice_id, amount, currency, status, failure_reason, payment_method, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pay_id, req.external_payment_id, req.customer_id, req.invoice_id or None,
             req.amount, req.currency, req.status, req.failure_reason, req.payment_method, now, now),
        )
        # Auto-reconcile if payment is successful
        if req.status in ("captured", "paid", "authorized") and req.invoice_id:
            conn.execute("UPDATE invoices SET status = 'paid', paid_at = ?, updated_at = ? WHERE id = ?",
                         (now, now, req.invoice_id))
            case = conn.execute(
                "SELECT id, amount_at_risk FROM recovery_cases WHERE invoice_id = ? AND status NOT IN ('recovered','stopped','failed') LIMIT 1",
                (req.invoice_id,)
            ).fetchone()
            if case:
                conn.execute(
                    "UPDATE recovery_cases SET status = 'recovered', amount_recovered = ?, stop_reason = 'PAYMENT_RECEIVED', updated_at = ? WHERE id = ?",
                    (req.amount, now, case["id"]),
                )
                conn.execute(
                    """
                    UPDATE revenue_at_risk SET risk_status = 'resolved', resolved_at = ?,
                    resolution_reason = 'PAYMENT_RECEIVED', updated_at = ?
                    WHERE id = (SELECT revenue_risk_id FROM recovery_cases WHERE id = ?)
                    """,
                    (now, now, case["id"]),
                )
        conn.commit()
        if req.status in ("captured", "paid", "authorized") and req.invoice_id and case:
            _audit("recovery_case", case["id"], "RECOVERY_COMPLETED",
                   f"Payment {pay_id} received: INR {req.amount:,.2f}",
                   {"payment_id": pay_id, "amount": req.amount})
    finally:
        conn.close()
    return {"payment_id": pay_id, "status": req.status}


@router.get("/payments", dependencies=[Depends(require_api_key)])
def list_payments(customer_id: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM payments WHERE 1=1"
        p: list = []
        if customer_id:
            q += " AND customer_id = ?"; p.append(customer_id)
        q += " ORDER BY created_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── Revenue Risk Events ─────────────────────────────────────────────────────

@router.post("/risk-events", dependencies=[Depends(require_api_key)])
def create_risk_event(req: CreateRiskEventRequest):
    """Register a revenue-risk event, creating a risk record and recovery case."""
    result = detect_and_create_risk(
        event_type=req.event_type,
        customer_id=req.customer_id,
        amount=req.amount,
        currency=req.currency,
        invoice_id=req.invoice_id,
        payment_id=req.payment_id,
        days_overdue=req.days_overdue,
    )
    return result


@router.get("/risk-events", dependencies=[Depends(require_api_key)])
def list_risk_events(status: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM revenue_at_risk WHERE 1=1"
        p: list = []
        if status:
            q += " AND risk_status = ?"; p.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── Recovery Cases ──────────────────────────────────────────────────────────

@router.get("/recovery-cases", dependencies=[Depends(require_api_key)])
def list_recovery_cases(status: Optional[str] = None, priority: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM recovery_cases WHERE 1=1"
        p: list = []
        if status:
            q += " AND status = ?"; p.append(status)
        if priority:
            q += " AND priority = ?"; p.append(priority)
        q += " ORDER BY risk_score DESC, created_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/recovery-cases/{case_id}", dependencies=[Depends(require_api_key)])
def get_recovery_case(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error": {"code": "CASE_NOT_FOUND", "message": f"Recovery case {case_id} not found."}})
    return case


@router.post("/recovery-cases/{case_id}/decide", dependencies=[Depends(require_api_key)])
def run_ai_decision_for_case(case_id: str):
    """Run the full AI decision + guardrail pipeline for a specific case."""
    context = build_case_context(case_id)
    if not context:
        raise HTTPException(status_code=404, detail={"error": {"code": "CASE_NOT_FOUND", "message": f"Case {case_id} not found."}})
    try:
        decision = make_recovery_decision(context)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail={"error": {"code": "AI_DECISION_FAILED", "message": str(exc)}})
    try:
        approved = guardrail_enforce(decision, context)
    except GuardrailViolation as gv:
        _audit("recovery_case", case_id, "ACTION_REJECTED", f"{gv.code}: {gv.message}")
        raise HTTPException(status_code=409, detail={"error": {"code": gv.code, "message": gv.message}})
    _audit("recovery_case", case_id, "AI_DECISION_MADE",
           f"Decision: {approved.decision}, Priority: {approved.priority}. {approved.reason}",
           {"decision": approved.model_dump()})
    return {"case_id": case_id, "decision": approved.model_dump()}


@router.post("/recovery-cases/{case_id}/payment-link", dependencies=[Depends(require_api_key)])
def create_case_payment_link(case_id: str):
    """Create a Razorpay payment link (test mode) for a recovery case."""
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error": {"code": "CASE_NOT_FOUND", "message": f"Case {case_id} not found."}})
    conn = get_db_connection()
    try:
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (case["customer_id"],)).fetchone()
    finally:
        conn.close()
    try:
        result = _create_plink(
            recovery_case_id=case_id,
            customer_id=case["customer_id"],
            amount=float(case["amount_at_risk"]),
            customer_email=dict(cust).get("email", "") if cust else "",
            customer_name=dict(cust).get("name", "") if cust else "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"error": {"code": "RAZORPAY_ERROR", "message": str(exc)}})
    return result


# ─── Promises ────────────────────────────────────────────────────────────────

@router.post("/promises", dependencies=[Depends(require_api_key)])
def create_promise_endpoint(req: CreatePromiseRequest):
    try:
        return create_promise(
            customer_id=req.customer_id,
            promised_amount=req.promised_amount,
            promised_date=req.promised_date,
            invoice_id=req.invoice_id,
            payment_id=req.payment_id,
            recovery_case_id=req.recovery_case_id,
            notes=req.notes,
        )
    except PromiseStateError as pse:
        raise HTTPException(status_code=422, detail={"error": {"code": pse.code, "message": pse.message}})


@router.get("/promises", dependencies=[Depends(require_api_key)])
def list_promises(customer_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM promise_to_pay WHERE 1=1"
        p: list = []
        if customer_id:
            q += " AND customer_id = ?"; p.append(customer_id)
        if status:
            q += " AND status = ?"; p.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/promises/{promise_id}", dependencies=[Depends(require_api_key)])
def get_promise_endpoint(promise_id: str):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM promise_to_pay WHERE id = ?", (promise_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "PROMISE_NOT_FOUND", "message": f"Promise {promise_id} not found."}})
    return dict(row)


@router.post("/promises/{promise_id}/fulfill", dependencies=[Depends(require_api_key)])
def fulfill_promise_endpoint(promise_id: str, req: FulfillPromiseRequest):
    """Fulfill a promise only when backed by a real successful payment record."""
    try:
        return fulfill_promise(promise_id, req.payment_id)
    except PromiseStateError as pse:
        sc = 404 if pse.code in ("PROMISE_NOT_FOUND", "PAYMENT_NOT_FOUND") else 409
        raise HTTPException(status_code=sc, detail={"error": {"code": pse.code, "message": pse.message}})


@router.post("/promises/{promise_id}/break", dependencies=[Depends(require_api_key)])
def break_promise_endpoint(promise_id: str, reason: str = "Customer did not pay"):
    try:
        return break_promise(promise_id, reason)
    except PromiseStateError as pse:
        raise HTTPException(status_code=409, detail={"error": {"code": pse.code, "message": pse.message}})


@router.post("/promises/{promise_id}/cancel", dependencies=[Depends(require_api_key)])
def cancel_promise_endpoint(promise_id: str):
    try:
        return cancel_promise(promise_id)
    except PromiseStateError as pse:
        raise HTTPException(status_code=409, detail={"error": {"code": pse.code, "message": pse.message}})


@router.post("/promises/check-overdue", dependencies=[Depends(require_api_key)])
def check_overdue_endpoint():
    return check_overdue_promises()


# ─── B2B Chaser ──────────────────────────────────────────────────────────────

@router.post("/b2b-chaser/run", dependencies=[Depends(require_api_key)])
def run_b2b_chaser_endpoint(max_cases: int = Query(50, le=200)):
    """Scan overdue invoices from the DB, generate LLM-personalised chasers."""
    try:
        return _run_b2b(max_cases=max_cases)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": {"code": "B2B_CHASER_ERROR", "message": str(exc)}})


# ─── Voice Recovery ───────────────────────────────────────────────────────────

@router.post("/voice-recovery", dependencies=[Depends(require_api_key)])
async def voice_recovery_endpoint(
    recovery_case_id: str = Query(...),
    customer_id: str = Query(...),
    audio: UploadFile = File(...),
):
    """
    Full voice recovery pipeline: Sarvam AI STT → Groq LLM intent → DB.
    Requires STT_API_KEY to be configured. Fails clearly if not.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_AUDIO", "message": "Uploaded audio file is empty."}})
    try:
        result = process_voice_audio(
            audio_bytes=audio_bytes,
            recovery_case_id=recovery_case_id,
            customer_id=customer_id,
            filename=audio.filename or "audio.wav",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"error": {"code": "STT_ERROR", "message": str(exc)}})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": {"code": "INTENT_PARSE_ERROR", "message": str(exc)}})
    return result.model_dump()


# ─── Batch Recovery ───────────────────────────────────────────────────────────

@router.post("/recovery/batch/run", dependencies=[Depends(require_api_key)])
def run_batch_endpoint(background_tasks: BackgroundTasks):
    """Trigger a full batch recovery run in background."""
    background_tasks.add_task(_run_batch)
    return {"message": "Batch recovery run triggered. Use /api/v2/recovery/batches to check status."}


@router.post("/recovery/batch/run-sync", dependencies=[Depends(require_api_key)])
def run_batch_sync():
    """Synchronous batch recovery run (for demo/testing)."""
    return _run_batch()


@router.get("/recovery/batch/{batch_id}", dependencies=[Depends(require_api_key)])
def get_batch_run(batch_id: str):
    b = _get_batch(batch_id)
    if not b:
        raise HTTPException(status_code=404, detail={"error": {"code": "BATCH_NOT_FOUND", "message": f"Batch {batch_id} not found."}})
    return b


@router.get("/recovery/batches", dependencies=[Depends(require_api_key)])
def list_batch_runs(limit: int = Query(20, le=100)):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM batch_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── Metrics ─────────────────────────────────────────────────────────────────

@router.get("/metrics/recovery")
def get_recovery_metrics():
    """Real-time KPIs derived entirely from actual database records."""
    return compute_recovery_metrics()


# ─── Audit Logs ──────────────────────────────────────────────────────────────

@router.get("/audit-logs", dependencies=[Depends(require_api_key)])
def get_audit_logs_v2(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM audit_logs WHERE 1=1"
        p: list = []
        if entity_type:
            q += " AND entity_type = ?"; p.append(entity_type)
        if entity_id:
            q += " AND entity_id = ?"; p.append(entity_id)
        q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"; p.extend([limit, offset])
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


# ─── Recovery Actions ─────────────────────────────────────────────────────────

@router.get("/recovery-actions", dependencies=[Depends(require_api_key)])
def list_recovery_actions(recovery_case_id: Optional[str] = None, limit: int = Query(50, le=200)):
    conn = get_db_connection()
    try:
        q = "SELECT * FROM recovery_actions WHERE 1=1"
        p: list = []
        if recovery_case_id:
            q += " AND recovery_case_id = ?"; p.append(recovery_case_id)
        q += " ORDER BY executed_at DESC LIMIT ?"; p.append(limit)
        rows = conn.execute(q, p).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
