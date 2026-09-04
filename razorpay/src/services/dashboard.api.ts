import api from '@/lib/api';

export interface RecoveryMetrics {
  revenue_at_risk: number;
  total_cases: number;
  open_cases: number;
  resolved_cases: number;
  total_recovery_cases: number;
  total_attempts: number;
  customers_contacted: number;
  successful_recoveries: number;
  total_recovered_amount: number;
  recovery_rate_pct: number;
  outstanding_revenue: number;
  escalated_cases: number;
  active_promises: number;
  overdue_promises: number;
  fulfilled_promises: number;
  fulfilled_promise_amount: number;
  recovered_amount_by_intervention: { action_type: string; count: number; attributed_recovered: number }[];
}

export const getDashboardMetrics = async (): Promise<RecoveryMetrics> => {
  const { data } = await api.get('/metrics/recovery');
  return data;
};

export const getAuditLogs = async (limit = 50, entityType?: string, entityId?: string): Promise<any[]> => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (entityType) params.set('entity_type', entityType);
  if (entityId) params.set('entity_id', entityId);
  const { data } = await api.get(`/audit-logs?${params}`);
  return Array.isArray(data) ? data : (data?.items ?? []);
};
