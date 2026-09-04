import api from '@/lib/api';

export const getPromises = async (customerId?: string, status?: string): Promise<any[]> => {
  const params = new URLSearchParams({ limit: '100' });
  if (customerId) params.set('customer_id', customerId);
  if (status) params.set('status', status);
  const { data } = await api.get(`/promises?${params}`);
  return Array.isArray(data) ? data : (data?.items ?? []);
};

export const getPromise = async (promiseId: string) => {
  const { data } = await api.get(`/promises/${promiseId}`);
  return data;
};

export const createPromise = async (payload: {
  customer_id: string;
  promised_amount: number;
  promised_date: string;
  invoice_id?: string;
  recovery_case_id?: string;
  notes?: string;
}) => {
  const { data } = await api.post('/promises', payload);
  return data;
};

export const fulfillPromise = async (promiseId: string, paymentId: string) => {
  const { data } = await api.post(`/promises/${promiseId}/fulfill`, { payment_id: paymentId });
  return data;
};

export const breakPromise = async (promiseId: string, reason: string) => {
  const { data } = await api.post(`/promises/${promiseId}/break`, null, { params: { reason } });
  return data;
};

export const cancelPromise = async (promiseId: string) => {
  const { data } = await api.post(`/promises/${promiseId}/cancel`);
  return data;
};

export const checkOverduePromises = async () => {
  const { data } = await api.post('/promises/check-overdue');
  return data;
};

export const getCustomers = async (): Promise<any[]> => {
  const { data } = await api.get('/customers');
  return Array.isArray(data) ? data : (data?.items ?? []);
};

export const getPayments = async (): Promise<any[]> => {
  const { data } = await api.get('/payments');
  return Array.isArray(data) ? data : (data?.items ?? []);
};

export const getRiskEvents = async (): Promise<any[]> => {
  const { data } = await api.get('/risk-events');
  return Array.isArray(data) ? data : (data?.items ?? []);
};

export const getBatchRuns = async (): Promise<any[]> => {
  const { data } = await api.get('/recovery/batches?limit=20');
  return Array.isArray(data) ? data : [];
};

export const runBatchSync = async () => {
  const { data } = await api.post('/recovery/batch/run-sync');
  return data;
};

export const runB2BChaser = async () => {
  const { data } = await api.post('/b2b-chaser/run');
  return data;
};

export const getInvoices = async (): Promise<any[]> => {
  const { data } = await api.get('/invoices?limit=100');
  return Array.isArray(data) ? data : (data?.items ?? []);
};
