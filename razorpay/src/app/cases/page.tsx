"use client"
import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { getRecoveryCases } from '@/services/recovery.api'
import { Badge } from '@/components/ui/badge'

const STATUS_COLOR: Record<string, string> = {
  recovered: 'text-emerald-400', open: 'text-amber-400', stopped: 'text-zinc-400',
  failed: 'text-red-400', escalated: 'text-red-400', in_progress: 'text-blue-400'
}

export default function RecoveryCasesPage() {
  const router = useRouter()
  const [status, setStatus] = useState('')

  const { data: cases = [], isLoading } = useQuery({
    queryKey: ['cases', status],
    queryFn: () => getRecoveryCases(status || undefined),
    refetchInterval: 15000,
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Recovery Cases</h1>
          <p className="text-muted-foreground text-sm mt-1">Click a case to run AI diagnosis and execute recovery actions</p>
        </div>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-100 text-sm px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        >
          <option value="" className="bg-zinc-900 text-zinc-100">All statuses</option>
          <option value="open" className="bg-zinc-900 text-zinc-100">Open</option>
          <option value="recovered" className="bg-zinc-900 text-zinc-100">Recovered</option>
          <option value="stopped" className="bg-zinc-900 text-zinc-100">Stopped</option>
          <option value="failed" className="bg-zinc-900 text-zinc-100">Failed</option>
        </select>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-muted-foreground text-center py-12">Loading…</p>
        ) : cases.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-12">
            No cases yet — go to Simulator to create one.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr className="text-xs text-muted-foreground uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Case ID</th>
                <th className="px-4 py-3 text-left">Risk Type</th>
                <th className="px-4 py-3 text-right">At Risk</th>
                <th className="px-4 py-3 text-right">Recovered</th>
                <th className="px-4 py-3 text-center">Priority</th>
                <th className="px-4 py-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {cases.map((c: any) => (
                <tr
                  key={c.id}
                  onClick={() => router.push(`/cases/${c.id}`)}
                  className="cursor-pointer hover:bg-muted/40 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-primary">{c.id}</td>
                  <td className="px-4 py-3 text-muted-foreground">{c.risk_type ?? '—'}</td>
                  <td className="px-4 py-3 text-right text-red-400 font-medium">
                    ₹{(c.amount_at_risk || 0).toLocaleString('en-IN')}
                  </td>
                  <td className="px-4 py-3 text-right text-emerald-400 font-medium">
                    ₹{(c.amount_recovered || 0).toLocaleString('en-IN')}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold ${
                      c.priority === 'HIGH' || c.priority === 'CRITICAL' ? 'text-red-400' :
                      c.priority === 'MEDIUM' ? 'text-amber-400' : 'text-zinc-400'
                    }`}>{c.priority}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold ${STATUS_COLOR[c.status] ?? 'text-zinc-400'}`}>
                      {c.status?.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
