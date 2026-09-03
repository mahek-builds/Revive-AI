# RecoverAI

AI Revenue Recovery Agent platform for Razorpay powered by a **Python FastAPI** backend.

## Directory Structure

```text
recoverAI/
├── README.md                           # Setup + how to run
├── .env.example                        # Shared environment template
├── .env                                # Local env (gitignored)
├── .gitignore                          # Git ignore list
├── requirements.txt                    # Python dependencies
├── package.json                        # Helper scripts
│
├── db/                                 # Shared DB layer
│   ├── schema.sql                      # Core 7 table schema
│   ├── migrations/                     # Database migrations
│   │   └── 001_initial.sql
│   └── seed_test_events.py             # Simulates Razorpay test mode events
│
├── backend/                            # Hirdesh's domain
│   ├── main.py                         # FastAPI app entrypoint
│   ├── database.py                     # SQLite database helpers
│   ├── webhooks/
│   │   ├── receiver.py                 # Signature verify & deduplication
│   │   └── eventParser.py              # Raw payload → revenue_at_risk row
│   ├── razorpay/
│   │   ├── client.py                   # Thin SDK wrapper & auth
│   │   ├── paymentsApi.py              # GET /payments/{id}, /orders/{id}/payments
│   │   ├── paymentLinksApi.py          # Create/send Payment Link
│   │   ├── invoicesApi.py             # Create/resend Invoice
│   │   ├── subscriptionsApi.py         # Retry & subscription helpers
│   │   └── getFailureContext.py        # Failure context for diagnosis
│   ├── executor/
│   │   ├── stoppingRules.py            # Max attempts, cooldown, opt-out, $ gate
│   │   ├── backoff.py                  # Exponential backoff on 429s
│   │   └── runIntervention.py          # Reads pending intervention & acts
│   ├── promiseToPay/
│   │   └── checker.py                  # Polls & updates promise statuses
│   └── metrics/
│       └── aggregate.py                # Dashboard metrics aggregate API
│
└── intelligence/                       # Mahek's domain
    ├── diagnosis/
    │   ├── rulesClassifier.py          # error_code → root_cause bucket
    │   └── llmClassifier.py            # Ambiguous-case fallback + confidence
    ├── decisionEngine/
    │   ├── decisionRules.py            # root_cause → action + channel + timing
    │   └── escalationLadder.py         # Day 0-3 / 4-14 / 15-30 / 30+ logic
    └── templates/
        └── messageTemplates.py         # Pre-approved message library
```

## How to Run

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

3. **Seed Database**:
   ```bash
   python -m db.seed_test_events
   # or
   npm run seed
   ```

4. **Start Python FastAPI Server**:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
   # or
   npm start
   ```
   Open `http://localhost:5000` in your browser.
