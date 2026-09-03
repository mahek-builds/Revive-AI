import React, { useState, useEffect, useRef } from 'react';
import { 
    LayoutDashboard, Activity, CreditCard, Brain, ShieldAlert, MessageSquare,
    RefreshCw, PlayCircle, AlertTriangle, CheckCircle2, TrendingUp, Loader,
    ShieldBan, Workflow, Rss, ExternalLink, Zap
} from 'lucide-react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);
ChartJS.defaults.color = '#cbd5e1';
ChartJS.defaults.font.family = 'Inter';

export default function App() {
    const [metrics, setMetrics] = useState({
        total_revenue_at_risk: 0,
        recovered_revenue: 0,
        recovery_rate_percent: 0,
        pending_interventions: 0
    });
    
    const [auditLogs, setAuditLogs] = useState([]);
    const [causeCounts, setCauseCounts] = useState({});
    const [eventCounts, setEventCounts] = useState({});
    
    const [paymentAmount, setPaymentAmount] = useState(1499);
    const [customerEmail, setCustomerEmail] = useState("alex.merchant@example.com");
    const [failureScenario, setFailureScenario] = useState("INSUFFICIENT_FUNDS");
    const [paymentStatus, setPaymentStatus] = useState("");
    const [isBatchRunning, setIsBatchRunning] = useState(false);
    
    // Pipeline State
    const [pipelineVisible, setPipelineVisible] = useState(false);
    const [pipelineGlobalMsg, setPipelineGlobalMsg] = useState("Running AI Agent Pipeline...");
    const [pipelineGlobalClass, setPipelineGlobalClass] = useState("badge-purple");
    
    const [pipelineNodes, setPipelineNodes] = useState([
        { id: 1, title: "Webhook Ingest", icon: <Rss size={18} />, statusClass: "waiting", badgeClass: "badge-blue", badgeText: "Waiting", desc: "Standing by...", meta: "—" },
        { id: 2, title: "AI Diagnosis", icon: <Brain size={18} />, statusClass: "waiting", badgeClass: "badge-blue", badgeText: "Waiting", desc: "Standing by...", meta: "—" },
        { id: 3, title: "Decision Engine", icon: <Activity size={18} />, statusClass: "waiting", badgeClass: "badge-blue", badgeText: "Waiting", desc: "Standing by...", meta: "—" },
        { id: 4, title: "Execution Agent", icon: <Zap size={18} />, statusClass: "waiting", badgeClass: "badge-blue", badgeText: "Waiting", desc: "Standing by...", meta: "—" }
    ]);

    const loadDashboardData = async () => {
        try {
            const resM = await fetch('/api/metrics');
            const dataM = await resM.json();
            setMetrics(dataM);
            
            const resA = await fetch('/api/audit-logs');
            const dataA = await resA.json();
            const logs = dataA.audit_logs || [];
            setAuditLogs(logs);
            
            const cCounts = {};
            const eCounts = {};
            logs.forEach(log => {
                const cause = log.root_cause || 'under_diagnosis';
                const evType = log.event_type || 'payment_failed';
                cCounts[cause] = (cCounts[cause] || 0) + 1;
                eCounts[evType] = (eCounts[evType] || 0) + 1;
            });
            setCauseCounts(cCounts);
            setEventCounts(eCounts);
        } catch (err) {
            console.error("Error loading dashboard data", err);
        }
    };

    useEffect(() => {
        loadDashboardData();
    }, []);

    const triggerBatchRun = async () => {
        setIsBatchRunning(true);
        try {
            await fetch('/api/seed', { method: 'POST' });
            await loadDashboardData();
        } catch (err) {
            console.error(err);
        } finally {
            setIsBatchRunning(false);
        }
    };

    const simulateCustomerPayment = async (rar_id) => {
        try {
            const res = await fetch(`/api/simulate-recovery/${rar_id}`, { method: 'POST' });
            if (res.ok) {
                await loadDashboardData();
            } else {
                console.error("Failed to simulate recovery");
            }
        } catch (err) {
            console.error(err);
        }
    };

    const updatePipelineNode = (idx, updates) => {
        setPipelineNodes(prev => prev.map(n => n.id === idx ? { ...n, ...updates } : n));
    };

    const resetPipeline = () => {
        setPipelineVisible(true);
        setPipelineGlobalMsg("Running AI Agent Pipeline...");
        setPipelineGlobalClass("badge-purple");
        setPipelineNodes(prev => prev.map(n => ({
            ...n, statusClass: "waiting", badgeClass: "badge-blue", badgeText: "Waiting", desc: "Standing by...", meta: "—"
        })));
    };

    const triggerSimulatedFailure = async (customParams = null) => {
        let amt = paymentAmount;
        let em = customerEmail;
        let scenario = failureScenario;
        let errCode = "BAD_REQUEST_PAYMENT_FAILED";
        let errDesc = "Payment failed due to insufficient balance in customer account";

        if (scenario === "HIGH_VALUE_THRESHOLD") {
            amt = 75000; setPaymentAmount(75000);
            errCode = "BAD_REQUEST_PAYMENT_FAILED";
            errDesc = "High-value enterprise payment failure requiring compliance review";
        } else if (scenario === "CARD_EXPIRED") {
            errCode = "BAD_REQUEST_CARD_EXPIRED";
            errDesc = "Card expiry date is in the past or card deactivated";
        } else if (scenario === "BANK_TIMEOUT") {
            errCode = "GATEWAY_TIMEOUT";
            errDesc = "Bank server authorization timeout occurred";
        } else if (scenario === "USER_ABANDONED") {
            errCode = "USER_ABANDONED";
            errDesc = "Customer closed Razorpay checkout modal before completing payment";
        }

        if (customParams) {
            if (customParams.amount) amt = customParams.amount;
            if (customParams.email) em = customParams.email;
            if (customParams.error_code) errCode = customParams.error_code;
            if (customParams.error_description) errDesc = customParams.error_description;
        }

        resetPipeline();
        setPaymentStatus("Simulating payment failure & invoking live autonomous recovery agent pipeline...");

        try {
            const res = await fetch('/api/simulate-payment-failure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    amount: amt,
                    customer_email: em,
                    error_code: errCode,
                    error_description: errDesc
                })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Pipeline invocation failed");

            const steps = data.steps || [];

            for (let i = 0; i < steps.length; i++) {
                const stepData = steps[i];
                const idx = stepData.step;

                updatePipelineNode(idx, { statusClass: "active", badgeClass: "badge-purple", badgeText: "Processing..." });
                await new Promise(r => setTimeout(r, 450));

                let statusClass = "completed";
                let badgeClass = "badge-success";
                let badgeText = "Done";

                if (stepData.status === "stopped") {
                    statusClass = "stopped"; badgeClass = "badge-warning"; badgeText = "Safeguard Fired";
                } else if (stepData.status !== "completed" && stepData.status !== "executed") {
                    badgeClass = "badge-blue"; badgeText = stepData.status.toUpperCase();
                }

                let metaTxt = "—";
                if (idx === 1) metaTxt = `Event ID: ${stepData.entity_id}`;
                if (idx === 2) metaTxt = `Cause: ${stepData.root_cause} | LLM Conf: ${Math.round(stepData.confidence_score*100)}%`;
                if (idx === 3) metaTxt = `Strategy: ${stepData.action} via ${stepData.channel.toUpperCase()}`;
                if (idx === 4) metaTxt = stepData.result ? (stepData.result.reason || "Recovery link generated") : "Completed";

                updatePipelineNode(idx, { statusClass, badgeClass, badgeText, desc: stepData.details, meta: metaTxt });
            }

            setPipelineGlobalMsg("Pipeline Execution Finished");
            setPipelineGlobalClass("badge-success");
            setPaymentStatus(`Pipeline Finished for ₹${amt.toLocaleString('en-IN')}: AI agents executed all stages.`);
            loadDashboardData();

        } catch (err) {
            setPaymentStatus(`Error running pipeline: ${err.message}`);
        }
    };

    const startPayment = async () => {
        if (!paymentAmount || paymentAmount <= 0) {
            setPaymentStatus('Please specify a valid amount in INR.');
            return;
        }

        setPaymentStatus('Generating secure Razorpay order...');
        try {
            const orderResponse = await fetch('/api/payments/create-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: paymentAmount, customer_email: customerEmail })
            });
            const order = await orderResponse.json();
            if (!orderResponse.ok) throw new Error(order.detail || 'Failed to create order');

            const checkout = new window.Razorpay({
                key: order.key_id,
                amount: order.amount,
                currency: order.currency,
                name: 'reviveai Platform',
                description: 'Revenue recovery demo transaction',
                order_id: order.order_id,
                prefill: { email: order.customer.email },
                handler: async function (response) {
                    setPaymentStatus('Verifying payment cryptographic signature...');
                    const result = await fetch('/api/payments/verify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(response)
                    });
                    const data = await result.json();
                    setPaymentStatus(result.ok ? `Payment verified & captured: ${data.payment_id}` : data.detail);
                    if (result.ok) loadDashboardData();
                },
                modal: {
                    ondismiss: () => {
                        setPaymentStatus('Transaction modal closed by user.');
                        triggerSimulatedFailure({
                            amount: paymentAmount,
                            email: customerEmail,
                            error_code: "USER_ABANDONED",
                            error_description: "Customer closed payment modal without attempting authorization"
                        });
                    }
                }
            });

            checkout.on('payment.failed', (evt) => {
                setPaymentStatus(evt.error.description || 'Payment execution failed.');
                triggerSimulatedFailure({
                    amount: paymentAmount,
                    email: customerEmail,
                    error_code: evt.error.code || "BAD_REQUEST_PAYMENT_FAILED",
                    error_description: evt.error.description || "Razorpay checkout authorization failed"
                });
            });

            checkout.open();
        } catch (err) {
            setPaymentStatus(err.message);
        }
    };

    const causeData = {
        labels: Object.keys(causeCounts).map(k => k.replace('_', ' ').toUpperCase()),
        datasets: [{
            data: Object.values(causeCounts),
            backgroundColor: ['#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
            borderColor: 'rgba(15, 23, 42, 0.8)',
            borderWidth: 2
        }]
    };

    const eventData = {
        labels: Object.keys(eventCounts).map(k => k.replace('_', ' ').toUpperCase()),
        datasets: [{
            label: 'Events Count',
            data: Object.values(eventCounts),
            backgroundColor: '#06b6d4',
            borderRadius: 4
        }]
    };

    return (
        <>
            <aside>
                <div className="logo-area">
                    <div className="logo-icon">R</div>
                    <div className="logo-text">reviveai</div>
                    <span className="logo-badge">PRO</span>
                </div>
                <div className="nav-section-title">Overview</div>
                <ul className="nav-menu">
                    <li className="nav-item active"><a href="#"><LayoutDashboard size={18} /> Executive View</a></li>
                    <li className="nav-item"><a href="#audit-section"><Activity size={18} /> Audit Log Feed</a></li>
                    <li className="nav-item"><a href="#simulator-section"><CreditCard size={18} /> Payment Sandbox</a></li>
                </ul>
                <div className="nav-section-title">Intelligence</div>
                <ul className="nav-menu">
                    <li className="nav-item"><a href="#"><Brain size={18} /> Diagnosis Classifier</a></li>
                    <li className="nav-item"><a href="#"><ShieldAlert size={18} /> Compliance Rules</a></li>
                    <li className="nav-item"><a href="#"><MessageSquare size={18} /> Communication Matrix</a></li>
                </ul>
            </aside>

            <main>
                <header>
                    <div className="header-title">
                        <h1>Find revenue that's slipping away and win it back.</h1>
                        <p>Autonomous agent detecting revenue at risk, diagnosing root causes, and executing bounded recovery workflows.</p>
                    </div>
                    <div className="action-group">
                        <button className="btn btn-secondary" onClick={loadDashboardData}>
                            <RefreshCw size={18} /> Sync Data
                        </button>
                        <button className="btn btn-primary" onClick={triggerBatchRun} disabled={isBatchRunning}>
                            {isBatchRunning ? <Loader size={18} className="spin" /> : <PlayCircle size={18} />}
                            {isBatchRunning ? "Running batch..." : "Run Batch Simulation"}
                        </button>
                    </div>
                </header>

                <div className="metrics-grid">
                    <div className="metric-card">
                        <div className="metric-header">
                            <span className="metric-title">Total Revenue at Risk</span>
                            <div className="metric-icon-bg" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}>
                                <AlertTriangle size={20} />
                            </div>
                        </div>
                        <div className="metric-value" style={{ background: 'linear-gradient(to right, #ef4444, #f87171)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            ₹{metrics.total_revenue_at_risk.toLocaleString('en-IN')}
                        </div>
                        <div className="metric-subtitle"><AlertTriangle size={14} /> Active failed transactions</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-header">
                            <span className="metric-title">Recovered Revenue</span>
                            <div className="metric-icon-bg" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
                                <CheckCircle2 size={20} />
                            </div>
                        </div>
                        <div className="metric-value" style={{ background: 'linear-gradient(to right, #10b981, #34d399)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            ₹{metrics.recovered_revenue.toLocaleString('en-IN')}
                        </div>
                        <div className="metric-subtitle"><span className="pulse-dot"></span> Reclaimed to merchant bank</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-header">
                            <span className="metric-title">Recovery Success Rate</span>
                            <div className="metric-icon-bg" style={{ background: 'var(--accent-light)', color: 'var(--accent-primary)' }}>
                                <TrendingUp size={20} />
                            </div>
                        </div>
                        <div className="metric-value" style={{ background: 'linear-gradient(to right, #06b6d4, #2dd4bf)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            {metrics.recovery_rate_percent}%
                        </div>
                        <div className="metric-subtitle"><TrendingUp size={14} /> AI autonomous efficiency</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-header">
                            <span className="metric-title">Pending Interventions</span>
                            <div className="metric-icon-bg" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>
                                <Loader size={20} />
                            </div>
                        </div>
                        <div className="metric-value">{metrics.pending_interventions}</div>
                        <div className="metric-subtitle"><ShieldAlert size={14} /> Scheduled recovery actions</div>
                    </div>
                </div>

                <div className="stopping-rule-card">
                    <div className="stopping-rule-icon">
                        <ShieldBan size={22} />
                    </div>
                    <div>
                        <h4 style={{ fontWeight: 700, color: '#fb923c' }}>Active Compliance Safeguard (Stopping Rule Fired)</h4>
                        <p style={{ fontSize: '0.875rem', color: '#fdba74', marginTop: 2 }}>
                            <strong>High-Value Protection Gate:</strong> Transaction <code>pay_test105</code> (INR 75,000.00) exceeded automated execution limit (₹50,000 threshold). System automatically flipped status to <span className="badge badge-warning">NEEDS_HUMAN_APPROVAL</span> to prevent compliance risk.
                        </p>
                    </div>
                </div>

                <div className="section-card" id="simulator-section">
                    <div className="section-header">
                        <div className="section-title">
                            <CreditCard style={{ color: 'var(--accent-primary)' }} size={24} />
                            Razorpay Checkout Sandbox & Autonomous Agent Pipeline Simulator
                        </div>
                        <span className="badge badge-blue">Real-Time Autonomous Agent Pipeline</span>
                    </div>
                    <div className="payment-form">
                        <div className="input-group">
                            <label className="input-label">Amount (INR)</label>
                            <input type="number" value={paymentAmount} onChange={e => setPaymentAmount(e.target.value)} className="input-field" />
                        </div>
                        <div className="input-group">
                            <label className="input-label">Customer Email</label>
                            <input type="email" value={customerEmail} onChange={e => setCustomerEmail(e.target.value)} className="input-field" />
                        </div>
                        <div className="input-group">
                            <label className="input-label">Simulated Failure Scenario</label>
                            <select value={failureScenario} onChange={e => setFailureScenario(e.target.value)} className="input-field">
                                <option value="INSUFFICIENT_FUNDS">Payment degradation → Insufficient Funds</option>
                                <option value="USER_ABANDONED">Checkout drop-off recovery</option>
                                <option value="CARD_EXPIRED">Failed-subscription recovery</option>
                                <option value="BANK_TIMEOUT">B2B receivables chaser</option>
                                <option value="HIGH_VALUE_THRESHOLD">Compliance safeguard limit (&gt;₹50k)</option>
                            </select>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignSelf: 'flex-end' }}>
                            <button className="btn btn-primary" onClick={startPayment}>
                                <ExternalLink size={18} /> Launch Checkout
                            </button>
                            <button className="btn" style={{ background: '#ef4444', color: 'white', border: 'none' }} onClick={() => triggerSimulatedFailure()}>
                                <Zap size={18} /> Simulate Payment Failure & Run Pipeline
                            </button>
                        </div>
                    </div>
                    <div style={{ marginTop: '1rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{paymentStatus}</div>

                    {pipelineVisible && (
                        <div className="pipeline-container" style={{ display: 'block' }}>
                            <div className="pipeline-header">
                                <div className="pipeline-title">
                                    <Workflow size={20} /> Live Autonomous Recovery Agent Pipeline Execution
                                </div>
                                <span className={`badge ${pipelineGlobalClass}`}>{pipelineGlobalMsg}</span>
                            </div>
                            <div className="pipeline-steps-grid">
                                {pipelineNodes.map(node => (
                                    <div key={node.id} className={`pipeline-node ${node.statusClass}`}>
                                        <div className="node-step-badge">
                                            <span>Step 0{node.id}</span>
                                            <span className={`badge ${node.badgeClass}`}>{node.badgeText}</span>
                                        </div>
                                        <div className="node-title">
                                            {node.icon} {node.title}
                                        </div>
                                        <div className="node-desc">{node.desc}</div>
                                        <div className="node-meta">{node.meta}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                <div className="charts-row">
                    <div className="chart-card">
                        <div className="section-header" style={{ marginBottom: '1rem' }}>
                            <div className="section-title" style={{ fontSize: '1rem' }}>Failure Source Distribution</div>
                        </div>
                        <div style={{ height: '220px' }}>
                            <Bar data={eventData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: 'rgba(255, 255, 255, 0.05)' } }, x: { grid: { display: false } } } }} />
                        </div>
                    </div>
                    <div className="chart-card">
                        <div className="section-header" style={{ marginBottom: '1rem' }}>
                            <div className="section-title" style={{ fontSize: '1rem' }}>AI Diagnosis Results</div>
                        </div>
                        <div style={{ height: '220px' }}>
                            <Doughnut data={causeData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }} />
                        </div>
                    </div>
                </div>

                <div className="section-card" id="audit-section" style={{ marginBottom: '4rem' }}>
                    <div className="section-header">
                        <div className="section-title">Audit Trail & Decision Sequence Log</div>
                        <span className="badge badge-purple">Real-Time Feed</span>
                    </div>
                    <div className="table-container">
                        <table className="custom-table">
                            <thead>
                                <tr>
                                    <th>Event Details</th>
                                    <th>Value at Risk</th>
                                    <th>AI Diagnosis & Heuristics</th>
                                    <th>Decided Action</th>
                                    <th>Delivery Channel</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {auditLogs.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                                            No event records found. Click "Run Batch Simulation" to generate.
                                        </td>
                                    </tr>
                                ) : (
                                    auditLogs.map((log, i) => {
                                        let statusBadge = <span className="badge badge-warning">{log.status}</span>;
                                        if (log.status === 'recovered') statusBadge = <span className="badge badge-success">Recovered</span>;
                                        if (log.intervention_status === 'stopped') statusBadge = <span className="badge badge-danger">Stopping Rule Fired</span>;
                                        return (
                                            <tr key={i}>
                                                <td>
                                                    <strong style={{ color: 'var(--accent-primary)' }}>{log.id}</strong>
                                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{log.event_type}</div>
                                                </td>
                                                <td><strong>₹{(log.amount || 0).toLocaleString('en-IN')}</strong></td>
                                                <td>
                                                    <div><span className="badge badge-blue">{log.root_cause || 'Diagnosing...'}</span></div>
                                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 2 }}>{log.error_description || ''}</div>
                                                </td>
                                                <td><strong>{log.action_type || 'Pending'}</strong></td>
                                                <td><span className="badge badge-purple">{log.channel || 'System'}</span></td>
                                                <td>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                        {statusBadge}
                                                        {log.status === 'open' && (
                                                            <button 
                                                                className="btn btn-primary" 
                                                                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                                                                onClick={() => simulateCustomerPayment(log.id)}
                                                            >
                                                                Simulate Pay
                                                            </button>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </>
    );
}
