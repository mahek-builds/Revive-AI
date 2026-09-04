"use client"
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { AlertTriangle, CheckCircle2, TrendingUp, Activity, Zap } from 'lucide-react'
import { getDashboardMetrics, getAuditLogs } from '@/services/dashboard.api'

const fmt = (n: number) =>
  n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` :
  n >= 1000   ? `₹${(n / 1000).toFixed(1)}K`   :
  `₹${(n || 0).toLocaleString('en-IN')}`

export default function DashboardPage() {
  const { data: m, isLoading, isError } = useQuery({
    queryKey: ['metrics'],
    queryFn: getDashboardMetrics,
    refetchInterval: 15000,
  })

  const { data: logs = [] } = useQuery({
    queryKey: ['audit-logs-dash'],
    queryFn: () => getAuditLogs(6),
    refetchInterval: 15000,
  })

  if (isLoading) return (
    <div className="flex h-64 items-center justify-center text-muted-foreground text-sm">
      Loading metrics…
    </div>
  )

  if (isError) return (
    <div className="flex h-64 items-center justify-center text-red-400 text-sm">
      ⚠ Backend unreachable — make sure the server is running on port 5000.
    </div>
  )

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Live revenue recovery overview</p>
      </div>

      {/* 3 main numbers */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Revenue at Risk',  value: fmt(m?.revenue_at_risk ?? 0),         icon: AlertTriangle,  color: 'text-red-400' },
          { label: 'Total Recovered',  value: fmt(m?.total_recovered_amount ?? 0),  icon: CheckCircle2,   color: 'text-emerald-400' },
          { label: 'Recovery Rate',    value: `${m?.recovery_rate_pct ?? 0}%`,      icon: TrendingUp,     color: 'text-cyan-400' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border bg-card p-5">
            <Icon className={`h-5 w-5 mb-3 ${color}`} />
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-sm text-muted-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Secondary numbers */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Open Cases',       value: m?.open_cases ?? 0 },
          { label: 'Recovered Cases',  value: m?.successful_recoveries ?? 0 },
          { label: 'Active Promises',  value: m?.active_promises ?? 0 },
          { label: 'Escalated',        value: m?.escalated_cases ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border bg-card p-4 text-center">
            <p className="text-xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Quick Actions</h2>
        <div className="flex gap-3">
          <Link href="/simulator"
            className="flex items-center gap-2 bg-primary text-primary-foreground rounded-lg px-4 py-2.5 text-sm font-medium hover:opacity-90 transition-opacity">
            <Zap className="h-4 w-4" /> Recovery Simulator
          </Link>
          <Link href="/cases"
            className="flex items-center gap-2 border rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors">
            <Activity className="h-4 w-4" /> View Cases
          </Link>
        </div>
      </div>

      {/* Recent audit events */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Recent Activity</h2>
          <Link href="/audit" className="text-xs text-muted-foreground hover:text-primary">View all →</Link>
        </div>
        <div className="rounded-xl border divide-y bg-card">
          {logs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No activity yet — run the simulator.</p>
          ) : logs.map((log: any, i: number) => (
            <div key={i} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium">{log.action}</p>
                <p className="text-xs text-muted-foreground">{log.entity_type} · {log.entity_id}</p>
              </div>
              <span className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
