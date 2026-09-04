import sys
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path so imports work regardless of working directory
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from backend.database import get_db_connection, init_db
from backend.razorpay.client import get_razorpay_client, KEY_ID
from backend.webhooks.receiver import verify_webhook_signature, is_duplicate_event
from backend.webhooks.eventParser import parse_webhook_payload
from backend.metrics.aggregate import compute_aggregate_metrics
from db.seed_test_events import seed_test_events

load_dotenv()

app = FastAPI(
    title="reviveai Platform",
    description="AI Revenue Recovery Platform for Razorpay",
    version="1.0.0"
)

# Enable CORS for dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"


class PaymentOrderRequest(BaseModel):
    amount: float = Field(gt=0, le=10000000)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    customer_name: str = Field(default="", max_length=100)
    customer_email: str = Field(default="", max_length=254)
    customer_contact: str = Field(default="", max_length=20)


class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class SimulateFailureRequest(BaseModel):
    amount: float = Field(gt=0, default=1499.0)
    customer_email: str = Field(default="alex.merchant@example.com")
    error_code: str = Field(default="BAD_REQUEST_PAYMENT_FAILED")
    error_description: str = Field(default="Payment failed due to insufficient funds in customer account")

# Include Track 03 v2 router
from backend.routes_v2 import router as v2_router
app.include_router(v2_router)

@app.on_event("startup")
def startup_event():
    """Initializes SQLite database schema on server startup and runs column migrations."""
    import sqlite3
    from backend.database import DB_PATH
    init_db()
    # Add new columns to existing tables if missing (idempotent)
    migrations = [
        "ALTER TABLE customers ADD COLUMN external_customer_id TEXT",
        "ALTER TABLE customers ADD COLUMN company_name TEXT",
        "ALTER TABLE customers ADD COLUMN customer_type TEXT",
        "ALTER TABLE customers ADD COLUMN updated_at DATETIME",
        "ALTER TABLE audit_logs ADD COLUMN metadata TEXT",
    ]
    conn = sqlite3.connect(str(DB_PATH))
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass  # Column already exists
    conn.commit()
    conn.close()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "online", "system": "reviveai Python FastAPI Platform"}

@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """
    Razorpay Webhook Endpoint:
    1. Verifies HMAC-SHA256 signature
    2. Deduplicates event
    3. Parses payload into revenue_at_risk database record
    """
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay webhook signature"
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload format"
        )

    event_id = str(payload.get("account_id", "")) + str(payload.get("created_at", "")) + str(payload.get("event", ""))
    if is_duplicate_event(event_id):
        return {"status": "ignored", "reason": "duplicate_event"}

    parsed_record = parse_webhook_payload(payload)

    conn = get_db_connection()
    cursor = conn.cursor()

    # If it's a successful payment recovery event, update status if existing or insert as recovered
    if parsed_record["status"] == "recovered":
        cursor.execute("""
            UPDATE revenue_at_risk SET status = 'recovered' WHERE razorpay_entity_id = ? OR customer_id = ?
        """, (parsed_record["razorpay_entity_id"], parsed_record["customer_id"]))
    
    cursor.execute("""
        INSERT INTO revenue_at_risk 
        (id, customer_id, event_type, amount, currency, razorpay_entity_id, error_code, error_description, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed_record["id"],
        parsed_record["customer_id"],
        parsed_record["event_type"],
        parsed_record["amount"],
        parsed_record["currency"],
        parsed_record["razorpay_entity_id"],
        parsed_record["error_code"],
        parsed_record["error_description"],
        parsed_record["status"]
    ))
    conn.commit()
    conn.close()

    return {"status": "processed", "record": parsed_record}

@app.get("/api/metrics")
def get_metrics():
    """Returns aggregated revenue metrics for dashboard."""
    try:
        metrics = compute_aggregate_metrics()
        return metrics
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute metrics: {str(err)}"
        )

@app.get("/api/audit-logs")
def get_audit_logs():
    """Returns recent audit logs for the dashboard live feed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.event_type, r.amount, r.currency, r.error_code, r.error_description, r.status, r.created_at,
               d.root_cause, d.confidence_score, d.reasoning,
               i.action_type, i.channel, i.status AS intervention_status
        FROM revenue_at_risk r
        LEFT JOIN diagnoses d ON r.id = d.revenue_at_risk_id
        LEFT JOIN interventions i ON r.id = i.revenue_at_risk_id
        ORDER BY r.created_at DESC LIMIT 50
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"audit_logs": rows}

@app.post("/api/interventions/run-all")
def run_all_interventions():
    """Processes pending interventions and runs execution & diagnosis."""
    from intelligence.diagnosis.llmClassifier import classify_error
    from intelligence.decisionEngine.decisionRules import decide_action_for_cause
    from backend.executor.runIntervention import execute_intervention
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Diagnose open revenue_at_risk items without diagnosis
    cursor.execute("""
        SELECT id, error_code, error_description, amount FROM revenue_at_risk WHERE id NOT IN (SELECT revenue_at_risk_id FROM diagnoses)
    """)
    unprocessed = cursor.fetchall()
    
    for item in unprocessed:
        diag = classify_error(item["error_code"] or "", item["error_description"] or "")
        diag_id = f"diag_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO diagnoses (id, revenue_at_risk_id, root_cause, classifier_type, confidence_score, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (diag_id, item["id"], diag["root_cause"], diag["classifier_type"], diag["confidence_score"], diag["reasoning"]))
        
        decision = decide_action_for_cause(diag["root_cause"])
        interv_id = f"int_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO interventions (id, revenue_at_risk_id, diagnosis_id, action_type, channel, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (interv_id, item["id"], diag_id, decision["action"], decision["channel"]))

        cursor.execute("""
            INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
            VALUES (?, 'revenue_at_risk', ?, 'DIAGNOSED_AND_DECIDED', ?)
        """, (f"aud_{uuid.uuid4().hex[:8]}", item["id"], f"Root cause: {diag['root_cause']} -> Action: {decision['action']} via {decision['channel']}"))

    # 2. Execute pending interventions
    cursor.execute("""
        SELECT i.id, i.action_type, i.channel, i.attempt_number, r.amount, r.razorpay_entity_id, r.id as rar_id
        FROM interventions i
        JOIN revenue_at_risk r ON i.revenue_at_risk_id = r.id
        WHERE i.status = 'pending'
    """)
    pending = cursor.fetchall()
    executed_count = 0
    stopped_count = 0
    
    for row in pending:
        interv_dict = dict(row)
        res = execute_intervention(interv_dict)
        new_status = res.get("status", "executed")
        cursor.execute("UPDATE interventions SET status = ?, executed_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, row["id"]))
        
        # Log to audit_logs
        cursor.execute("""
            INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
            VALUES (?, 'intervention', ?, ?, ?)
        """, (f"aud_{uuid.uuid4().hex[:8]}", row["id"], f"ACTION_{new_status.upper()}", res.get("reason") or res.get("error") or "Executed successfully via Razorpay API"))
        
        if new_status == "executed":
            executed_count += 1
        elif new_status == "stopped":
            stopped_count += 1
            
    conn.commit()
    conn.close()
    return {"executed": executed_count, "stopped": stopped_count, "diagnosed": len(unprocessed)}

@app.post("/api/seed")
def trigger_seed():
    """Triggers test event database seeding."""
    try:
        seed_test_events()
        # Auto-run diagnosis & decision pipeline on seeded events
        run_all_interventions()
        return {"status": "success", "message": "Simulated Razorpay test events seeded & pipeline executed successfully"}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seeding failed: {str(err)}"
        )


@app.post("/api/payments/create-order")
def create_payment_order(payment: PaymentOrderRequest):
    """Creates a Razorpay order; the secret key never leaves the server."""
    try:
        client = get_razorpay_client()
        order = client.order.create({
            "amount": int(round(payment.amount * 100)),
            "currency": payment.currency.upper(),
            "receipt": f"reviveai_{uuid.uuid4().hex[:16]}",
            "notes": {"source": "reviveai_dashboard"}
        })
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": KEY_ID,
            "customer": {
                "name": payment.customer_name,
                "email": payment.customer_email,
                "contact": payment.customer_contact,
            },
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to create Razorpay order: {str(err)}"
        )


@app.post("/api/payments/verify")
def verify_payment(payment: PaymentVerificationRequest):
    """Verifies the Checkout signature using Razorpay's server-side SDK and records the successful payment."""
    try:
        client = get_razorpay_client()
        client.utility.verify_payment_signature({
            "razorpay_order_id": payment.razorpay_order_id,
            "razorpay_payment_id": payment.razorpay_payment_id,
            "razorpay_signature": payment.razorpay_signature,
        })
        
        # Fetch dynamic amount from Razorpay API
        try:
            rzp_payment = client.payment.fetch(payment.razorpay_payment_id)
            actual_amount = float(rzp_payment.get("amount", 0)) / 100.0
            actual_currency = rzp_payment.get("currency", "INR")
            actual_method = rzp_payment.get("method", "razorpay")
        except Exception:
            actual_amount = 0.0
            actual_currency = "INR"
            actual_method = "razorpay"

        # Record the successful payment in SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO payments 
            (id, external_payment_id, amount, currency, status, payment_method, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'captured', ?, ?, ?)
        """, (payment.razorpay_payment_id, payment.razorpay_order_id, actual_amount, actual_currency, actual_method, now, now))
        
        cursor.execute("""
            INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
            VALUES (?, 'payment', ?, 'PAYMENT_CAPTURED', ?)
        """, (f"aud_{uuid.uuid4().hex[:8]}", payment.razorpay_payment_id, f"Razorpay Payment {payment.razorpay_payment_id} captured (â‚¹{actual_amount:,.2f}) for Order {payment.razorpay_order_id}"))
        
        conn.commit()
        conn.close()
        
        return {"status": "verified", "payment_id": payment.razorpay_payment_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Razorpay payment verification failed: {str(e)}"
        )

@app.post("/api/simulate-payment-failure")
def simulate_payment_failure(req: SimulateFailureRequest):
    """
    Simulates a payment failure event and runs the live autonomous 4-step AI agent pipeline.
    Returns step-by-step pipeline execution telemetry.
    """
    from intelligence.diagnosis.llmClassifier import classify_error
    from intelligence.decisionEngine.decisionRules import decide_action_for_cause
    from backend.executor.runIntervention import execute_intervention

    rar_id = f"pay_fail_{uuid.uuid4().hex[:8]}"
    customer_id = f"cust_{uuid.uuid4().hex[:6]}"
    razorpay_entity_id = f"pay_{uuid.uuid4().hex[:10]}"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Step 1: Webhook Ingestion Agent
    cursor.execute("""
        INSERT INTO revenue_at_risk 
        (id, customer_id, event_type, amount, currency, razorpay_entity_id, error_code, error_description, status) 
        VALUES (?, ?, 'payment_failed', ?, 'INR', ?, ?, ?, 'open')
    """, (rar_id, customer_id, req.amount, razorpay_entity_id, req.error_code, req.error_description))

    cursor.execute("""
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'revenue_at_risk', ?, 'WEBHOOK_INGESTED', ?)
    """, (f"aud_{uuid.uuid4().hex[:8]}", rar_id, f"Captured payment.failed event for â‚¹{req.amount:,.2f} ({req.error_code})"))

    step1 = {
        "step": 1,
        "name": "Ingestion Agent",
        "status": "completed",
        "title": "Webhook Event Ingested",
        "details": f"Registered payment.failed event #{rar_id} for â‚¹{req.amount:,.2f}",
        "entity_id": rar_id
    }

    # Step 2: AI Diagnosis Agent
    diag = classify_error(req.error_code, req.error_description)
    diag_id = f"diag_{uuid.uuid4().hex[:8]}"
    cursor.execute("""
        INSERT INTO diagnoses (id, revenue_at_risk_id, root_cause, classifier_type, confidence_score, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (diag_id, rar_id, diag["root_cause"], diag["classifier_type"], diag["confidence_score"], diag["reasoning"]))

    cursor.execute("""
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'diagnosis', ?, 'AI_DIAGNOSED', ?)
    """, (f"aud_{uuid.uuid4().hex[:8]}", diag_id, f"Root cause: {diag['root_cause']} (Confidence: {int(diag['confidence_score']*100)}%)"))

    step2 = {
        "step": 2,
        "name": "AI Diagnosis Agent",
        "status": "completed",
        "root_cause": diag["root_cause"],
        "confidence_score": diag["confidence_score"],
        "classifier_type": diag["classifier_type"],
        "reasoning": diag["reasoning"],
        "title": "Root Cause Diagnosed",
        "details": f"Identified '{diag['root_cause']}' with {int(diag['confidence_score']*100)}% confidence"
    }

    # Step 3: Decision Engine Agent
    decision = decide_action_for_cause(diag["root_cause"])
    interv_id = f"int_{uuid.uuid4().hex[:8]}"
    cursor.execute("""
        INSERT INTO interventions (id, revenue_at_risk_id, diagnosis_id, action_type, channel, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (interv_id, rar_id, diag_id, decision["action"], decision["channel"]))

    cursor.execute("""
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'decision', ?, 'ACTION_DECIDED', ?)
    """, (f"aud_{uuid.uuid4().hex[:8]}", interv_id, f"Policy selected action '{decision['action']}' via {decision['channel']} channel"))

    step3 = {
        "step": 3,
        "name": "Decision Engine Agent",
        "status": "completed",
        "action": decision["action"],
        "channel": decision["channel"],
        "delay_minutes": decision.get("delay_minutes", 0),
        "title": "Strategy & Policy Selected",
        "details": f"Decided '{decision['action']}' dispatched via {decision['channel'].upper()}"
    }

    # Step 4: Autonomous Execution Agent
    interv_dict = {
        "id": interv_id,
        "action_type": decision["action"],
        "channel": decision["channel"],
        "attempt_number": 1,
        "amount": req.amount,
        "customer_email": req.customer_email,
        "razorpay_entity_id": razorpay_entity_id,
        "rar_id": rar_id
    }
    exec_res = execute_intervention(interv_dict)
    exec_status = exec_res.get("status", "executed")

    cursor.execute("UPDATE interventions SET status = ?, executed_at = CURRENT_TIMESTAMP WHERE id = ?", (exec_status, interv_id))

    cursor.execute("""
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'intervention', ?, ?, ?)
    """, (f"aud_{uuid.uuid4().hex[:8]}", interv_id, f"ACTION_{exec_status.upper()}", exec_res.get("reason") or exec_res.get("error") or "Executed Razorpay payment link recovery"))

    conn.commit()
    conn.close()

    step4 = {
        "step": 4,
        "name": "Autonomous Execution Agent",
        "status": exec_status,
        "title": "Intervention Executed" if exec_status == "executed" else ("Stopping Rule Triggered" if exec_status == "stopped" else "Execution Result"),
        "details": exec_res.get("reason") or exec_res.get("error") or f"Dispatched recovery action successfully via {decision['channel'].upper()}",
        "result": exec_res
    }

    return {
        "status": "success",
        "pipeline_id": rar_id,
        "steps": [step1, step2, step3, step4]
    }

@app.post("/api/simulate-recovery/{rar_id}")
def simulate_customer_recovery(rar_id: str):
    """
    Demo endpoint: Simulates a customer clicking and successfully paying a recovery link.
    Updates the database to mark the revenue_at_risk status as 'recovered'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify rar exists
    cursor.execute("SELECT id FROM revenue_at_risk WHERE id = ?", (rar_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Revenue at risk record not found")

    # Update status to recovered
    cursor.execute("UPDATE revenue_at_risk SET status = 'recovered' WHERE id = ?", (rar_id,))
    
    # Add audit log
    cursor.execute("""
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'revenue_at_risk', ?, 'STATUS_RECOVERED', ?)
    """, (f"aud_{uuid.uuid4().hex[:8]}", rar_id, "Customer successfully completed payment via recovery link!"))

    conn.commit()
    conn.close()

    return {"status": "success", "message": f"Successfully simulated customer recovery for {rar_id}"}

# ---- New Promise-to-Pay Endpoints ----
from backend.promiseToPay.checker import check_promise_statuses

@app.get("/api/promise-to-pay/check")
def promise_to_pay_check():
    """Runs the promise-to-pay status checker and returns summary."""
    result = check_promise_statuses()
    return result

@app.post("/api/promise-to-pay/create")
def promise_to_pay_create(customer_id: str, promised_date: str, intervention_id: str):
    """Creates a new promise-to-pay record linked to an intervention.

    Args:
        customer_id: ID of the customer.
        promised_date: ISOâ€‘8601 datetime string for promised payment.
        intervention_id: ID of the related intervention.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    promise_id = f"ppt_{uuid.uuid4().hex[:8]}"
    cursor.execute(
        """
        INSERT INTO promise_to_pay (id, intervention_id, promised_date, status)
        VALUES (?, ?, ?, 'pending')
        """,
        (promise_id, intervention_id, promised_date)
    )
    cursor.execute(
        """
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'promise_to_pay', ?, 'CREATED', ?)
        """,
        (f"aud_{uuid.uuid4().hex[:8]}", promise_id, f"Created promise for intervention {intervention_id}")
    )
    conn.commit()
    conn.close()
    return {"status": "created", "promise_id": promise_id}

# ---- B2B Receivables Chaser ----
@app.post("/api/b2b-chaser/run")
def run_b2b_chaser():
    """Scans open revenueâ€‘atâ€‘risk rows older than 7 days, creates a placeholder intervention and linked promiseâ€‘toâ€‘pay.
    Returns count of promises created.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, customer_id, amount FROM revenue_at_risk
        WHERE status = 'open' AND created_at < datetime('now', '-7 days')
        """
    )
    rows = cursor.fetchall()
    created = 0
    for row in rows:
        # Create a placeholder intervention (send payment link)
        interv_id = f"int_{uuid.uuid4().hex[:8]}"
        cursor.execute(
            """
            INSERT INTO interventions (id, revenue_at_risk_id, diagnosis_id, action_type, channel, status)
            VALUES (?, ?, ?, 'send_payment_link', 'email', 'pending')
            """,
            (interv_id, row["id"], None)
        )
        # Create a promise to pay, due in 5 days
        promised_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
        promise_id = f"ppt_{uuid.uuid4().hex[:8]}"
        cursor.execute(
            """
            INSERT INTO promise_to_pay (id, intervention_id, promised_date, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (promise_id, interv_id, promised_date)
        )
        cursor.execute(
            """
            INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
            VALUES (?, 'b2b_chaser', ?, 'PROMISE_CREATED', ?)
            """,
            (f"aud_{uuid.uuid4().hex[:8]}", promise_id, f"Created promise for RAR {row['id']}")
        )
        created += 1
    conn.commit()
    conn.close()
    return {"created_promises": created}

# ---- Hinglish Voice Recovery (Placeholder) ----
@app.post("/api/voice-recovery")
def voice_recovery(transcript: str, customer_id: str):
    """Accepts a Hinglish transcript, runs LLM classification, and creates a recovery intervention.
    This is a stub implementation.
    """
    from intelligence.diagnosis.llmClassifier import classify_error
    diag = classify_error("UNKNOWN_ERROR", transcript)
    from intelligence.decisionEngine.decisionRules import decide_action_for_cause
    decision = decide_action_for_cause(diag["root_cause"])
    # Insert a dummy revenue_at_risk entry
    conn = get_db_connection()
    cursor = conn.cursor()
    rar_id = f"rar_{uuid.uuid4().hex[:8]}"
    cursor.execute(
        """
        INSERT INTO revenue_at_risk (id, customer_id, event_type, amount, currency, razorpay_entity_id, error_code, error_description, status)
        VALUES (?, ?, 'voice_recovery', 0, 'INR', '', 'VOICE_TRANSCRIPT', ?, 'open')
        """,
        (rar_id, customer_id, transcript)
    )
    # Insert diagnosis
    diag_id = f"diag_{uuid.uuid4().hex[:8]}"
    cursor.execute(
        """
        INSERT INTO diagnoses (id, revenue_at_risk_id, root_cause, classifier_type, confidence_score, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (diag_id, rar_id, diag["root_cause"], diag["classifier_type"], diag["confidence_score"], diag["reasoning"]))
    # Insert intervention
    interv_id = f"int_{uuid.uuid4().hex[:8]}"
    cursor.execute(
        """
        INSERT INTO interventions (id, revenue_at_risk_id, diagnosis_id, action_type, channel, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """,
        (interv_id, rar_id, diag_id, decision["action"], decision["channel"]))
    cursor.execute(
        """
        INSERT INTO audit_logs (id, entity_type, entity_id, action, details)
        VALUES (?, 'voice_recovery', ?, 'INTERVENTION_CREATED', ?)
        """,
        (f"aud_{uuid.uuid4().hex[:8]}", interv_id, f"Voice recovery created action {decision['action']}")
    )
    conn.commit()
    conn.close()
    return {"status": "created", "rar_id": rar_id, "intervention_id": interv_id}

# Serve static frontend web application

# Serve static frontend web application
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    @app.get("/")
    def read_root():
        index_page = FRONTEND_DIR / "pages" / "index.html"
        if index_page.exists():
            return FileResponse(index_page)
        return {"message": "reviveai Python Platform running."}

