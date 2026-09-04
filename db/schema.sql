-- reviveai Database Schema (extended for Track 03)

-- Extended customers table
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    external_customer_id TEXT,
    name TEXT,
    email TEXT,
    phone TEXT,
    company_name TEXT,
    customer_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    external_invoice_id TEXT,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'INR',
    status TEXT DEFAULT 'unpaid',
    due_date DATETIME,
    paid_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    external_payment_id TEXT,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'INR',
    status TEXT DEFAULT 'pending',
    failure_reason TEXT,
    payment_method TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Revenue at risk (extended)
CREATE TABLE IF NOT EXISTS revenue_at_risk (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
    payment_id TEXT REFERENCES payments(id) ON DELETE SET NULL,
    risk_type TEXT NOT NULL,
    amount_at_risk REAL NOT NULL,
    risk_score REAL DEFAULT 0.5,
    risk_status TEXT DEFAULT 'open',
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    resolution_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Recovery cases
CREATE TABLE IF NOT EXISTS recovery_cases (
    id TEXT PRIMARY KEY,
    revenue_risk_id TEXT REFERENCES revenue_at_risk(id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
    payment_id TEXT REFERENCES payments(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    risk_score REAL DEFAULT 0.5,
    amount_at_risk REAL DEFAULT 0,
    amount_recovered REAL DEFAULT 0,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 5,
    escalation_level INTEGER DEFAULT 0,
    max_escalation_level INTEGER DEFAULT 3,
    last_action TEXT,
    next_action_at DATETIME,
    stop_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Extended promise_to_pay table
CREATE TABLE IF NOT EXISTS promise_to_pay (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
    payment_id TEXT REFERENCES payments(id) ON DELETE SET NULL,
    recovery_case_id TEXT REFERENCES recovery_cases(id) ON DELETE SET NULL,
    promised_amount REAL NOT NULL,
    promised_date DATETIME NOT NULL,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    fulfilled_at DATETIME,
    broken_at DATETIME
);

-- Voice recovery sessions
CREATE TABLE IF NOT EXISTS voice_recovery_sessions (
    id TEXT PRIMARY KEY,
    recovery_case_id TEXT REFERENCES recovery_cases(id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    phone TEXT,
    provider TEXT,
    call_reference TEXT,
    audio_reference TEXT,
    transcript TEXT,
    language TEXT,
    detected_intent TEXT,
    confidence REAL,
    extracted_amount REAL,
    extracted_date DATETIME,
    action_taken TEXT,
    outcome TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- Recovery actions
CREATE TABLE IF NOT EXISTS recovery_actions (
    id TEXT PRIMARY KEY,
    recovery_case_id TEXT REFERENCES recovery_cases(id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    channel TEXT,
    status TEXT DEFAULT 'pending',
    reason TEXT,
    attempt_number INTEGER DEFAULT 1,
    escalation_level INTEGER DEFAULT 0,
    external_reference TEXT,
    executed_at DATETIME,
    completed_at DATETIME,
    failure_reason TEXT
);

-- Processed events for idempotency
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Batch recovery runs
CREATE TABLE IF NOT EXISTS batch_runs (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'running',
    cases_processed INTEGER DEFAULT 0,
    actions_executed INTEGER DEFAULT 0,
    amount_at_risk REAL DEFAULT 0,
    amount_recovered REAL DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- Legacy diagnoses table
CREATE TABLE IF NOT EXISTS diagnoses (
    id TEXT PRIMARY KEY,
    revenue_at_risk_id TEXT REFERENCES revenue_at_risk(id),
    root_cause TEXT NOT NULL,
    classifier_type TEXT NOT NULL,
    confidence_score REAL,
    reasoning TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Legacy interventions table
CREATE TABLE IF NOT EXISTS interventions (
    id TEXT PRIMARY KEY,
    revenue_at_risk_id TEXT REFERENCES revenue_at_risk(id),
    diagnosis_id TEXT REFERENCES diagnoses(id),
    action_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_at DATETIME,
    executed_at DATETIME,
    attempt_number INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppressions (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    reason TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
