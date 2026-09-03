-- Migration 001: Initial Schema Setup
-- Creating 7 core tables for RecoverAI

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    phone TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS revenue_at_risk (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    event_type TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'INR',
    razorpay_entity_id TEXT,
    error_code TEXT,
    error_description TEXT,
    status TEXT DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id TEXT PRIMARY KEY,
    revenue_at_risk_id TEXT REFERENCES revenue_at_risk(id),
    root_cause TEXT NOT NULL,
    classifier_type TEXT NOT NULL,
    confidence_score REAL,
    reasoning TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS promise_to_pay (
    id TEXT PRIMARY KEY,
    intervention_id TEXT REFERENCES interventions(id),
    promised_date DATETIME NOT NULL,
    status TEXT DEFAULT 'pending',
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
