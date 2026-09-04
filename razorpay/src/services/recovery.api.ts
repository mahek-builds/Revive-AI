import api from '@/lib/api';

export const getRecoveryCases = async (status?: string, priority?: string) => {
  const params = new URLSearchParams({ limit: '100' });
  if (status) params.set('status', status);
  if (priority) params.set('priority', priority);
  const { data } = await api.get(`/recovery-cases?${params}`);
  return Array.isArray(data) ? data : [];
};

export const getRecoveryCase = async (caseId: string) => {
  const { data } = await api.get(`/recovery-cases/${caseId}`);
  return data;
};

export const runAIDecision = async (caseId: string) => {
  const { data } = await api.post(`/recovery-cases/${caseId}/decide`);
  return data;
};

export const generatePaymentLink = async (caseId: string) => {
  const { data } = await api.post(`/recovery-cases/${caseId}/payment-link`);
  return data;
};

export const getRecoveryActions = async (caseId?: string) => {
  const params = new URLSearchParams({ limit: '100' });
  if (caseId) params.set('recovery_case_id', caseId);
  const { data } = await api.get(`/recovery-actions?${params}`);
  return Array.isArray(data) ? data : [];
};

export const runDemoFlow = async (amount: number, email: string, scenario: string = 'PAYMENT_FAILURE') => {
  const daysOverdue = scenario === 'OVERDUE_INVOICE' ? 30 : 5;
  const evtType = scenario === 'CHECKOUT_ABANDON' ? 'checkout.abandoned'
                : scenario === 'OVERDUE_INVOICE'  ? 'payment.error'
                : 'invoice.payment_failed';

  const custRes = await api.post('/customers', {
    name: 'Simulated Customer', email, phone: '+919876543210'
  });
  const cust = custRes.data;

  const due = new Date();
  if (scenario === 'OVERDUE_INVOICE') due.setDate(due.getDate() - 30);
  const invRes = await api.post('/invoices', {
    customer_id: cust.customer_id, amount, currency: 'INR', due_date: due.toISOString()
  });
  const inv = invRes.data;

  const riskRes = await api.post('/risk-events', {
    event_type: evtType, customer_id: cust.customer_id,
    invoice_id: inv.invoice_id, amount, currency: 'INR', days_overdue: daysOverdue
  });
  const risk = riskRes.data;

  const decideRes = await api.post(`/recovery-cases/${risk.case_id}/decide`);
  return decideRes.data;
};
