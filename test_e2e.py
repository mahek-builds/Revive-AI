import httpx, json, sys
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:8000"

def check(r, label):
    if r.status_code not in (200, 201):
        print(f"FAIL at {label}: {r.status_code} {r.text[:300]}")
        sys.exit(1)
    return r.json()

print("=== E2E Test: reviveai Track 03 ===")

# 1. Create customer
r = httpx.post(f"{BASE}/api/v2/customers", json={
    "name": "Rajesh Khanna",
    "email": "rajesh.khanna@example.com",
    "phone": "+919876543210",
    "company_name": "Khanna Industries Pvt Ltd",
    "customer_type": "business",
    "external_customer_id": "rzp_cust_test_001",
})
cust = check(r, "create_customer")
customer_id = cust["customer_id"]
print(f"1. Customer created: {customer_id}")

# 2. Create overdue invoice
due_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
r = httpx.post(f"{BASE}/api/v2/invoices", json={
    "customer_id": customer_id,
    "amount": 75000.00,
    "currency": "INR",
    "external_invoice_id": "INV-TEST-2026-001",
    "status": "unpaid",
    "due_date": due_date,
})
inv = check(r, "create_invoice")
invoice_id = inv["invoice_id"]
print(f"2. Invoice created: {invoice_id} (30 days overdue)")

# 3. Register revenue risk event
r = httpx.post(f"{BASE}/api/v2/risk-events", json={
    "event_type": "invoice.payment_failed",
    "customer_id": customer_id,
    "amount": 75000.00,
    "currency": "INR",
    "invoice_id": invoice_id,
    "days_overdue": 30,
})
risk = check(r, "risk_event")
case_id = risk["case_id"]
print(f"3. Risk detected: type={risk['risk_type']} score={risk['risk_score']} case={case_id}")

# 4. Run AI decision (real Groq call)
r = httpx.post(f"{BASE}/api/v2/recovery-cases/{case_id}/decide", timeout=30)
dec = check(r, "ai_decision")
d = dec["decision"]
print(f"4. AI Decision: {d['decision']} priority={d['priority']}")
print(f"   Reason: {d['reason'][:100]}")

# 5. Create payment link via Razorpay (real test mode)
r = httpx.post(f"{BASE}/api/v2/recovery-cases/{case_id}/payment-link", timeout=15)
if r.status_code == 200:
    plink = r.json()
    print(f"5. Payment link created: {plink.get('short_url', 'N/A')}")
else:
    print(f"5. Payment link: {r.status_code} {r.text[:200]} (non-fatal)")

# 6. Create promise to pay
promise_date = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
r = httpx.post(f"{BASE}/api/v2/promises", json={
    "customer_id": customer_id,
    "invoice_id": invoice_id,
    "recovery_case_id": case_id,
    "promised_amount": 75000.00,
    "promised_date": promise_date,
    "notes": "Customer promised to pay by end of week",
})
promise = check(r, "create_promise")
promise_id = promise["promise_id"]
print(f"6. Promise created: {promise_id}")

# 7. Record actual payment (simulating Razorpay captured event)
r = httpx.post(f"{BASE}/api/v2/payments", json={
    "customer_id": customer_id,
    "invoice_id": invoice_id,
    "external_payment_id": "pay_test_RZP123456",
    "amount": 75000.00,
    "currency": "INR",
    "status": "captured",
    "payment_method": "upi",
})
pay = check(r, "record_payment")
payment_id = pay["payment_id"]
print(f"7. Payment recorded: {payment_id}")

# 8. Fulfill promise backed by real payment
r = httpx.post(f"{BASE}/api/v2/promises/{promise_id}/fulfill", json={"payment_id": payment_id})
fulfilled = check(r, "fulfill_promise")
print(f"8. Promise fulfilled: {fulfilled}")

# 9. Recovery metrics
r = httpx.get(f"{BASE}/api/v2/metrics/recovery")
metrics = check(r, "metrics")
print(f"9. Recovery Metrics:")
print(f"   Revenue at Risk:     INR {metrics['revenue_at_risk']:,.2f}")
print(f"   Total Recovered:     INR {metrics['total_recovered_amount']:,.2f}")
print(f"   Recovery Rate:       {metrics['recovery_rate_pct']}%")
print(f"   Active Promises:     {metrics['active_promises']}")
print(f"   Fulfilled Promises:  {metrics['fulfilled_promises']}")
print(f"   Customers Contacted: {metrics['customers_contacted']}")

# 10. Audit trail
r = httpx.get(f"{BASE}/api/v2/audit-logs?entity_id={case_id}&limit=20")
audit = check(r, "audit_logs")
print(f"10. Audit trail ({audit['total']} entries for case):")
for item in audit["items"]:
    print(f"    [{item['action']}] {item['details'][:80]}")

print()
print("=== E2E TEST PASSED ===")
