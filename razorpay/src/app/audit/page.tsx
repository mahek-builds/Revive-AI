"use client"
import { useQuery } from '@tanstack/react-query'
import { getAuditLogs } from '@/services/dashboard.api'

export default function AuditPage() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['audit-logs-full'],
    queryFn: () => getAuditLogs(100),
    refetchInterval: 15000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <p className="text-muted-foreground text-sm mt-1">Every AI action, decision, and outcome — recorded automatically</p>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-muted-foreground text-center py-12">Loading…</p>
        ) : logs.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-12">No audit events yet. Run the simulator.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr className="text-xs text-muted-foreground uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Action</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Entity ID</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {logs.map((log: any, i: number) => (
                <tr key={i} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 font-medium">{log.action}</td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">{log.entity_type}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-primary">{log.entity_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
