"use client"
import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Brain, Link2, Loader2 } from 'lucide-react'
import { getRecoveryCase, runAIDecision, generatePaymentLink, syncPaymentLink, getRecoveryActions } from '@/services/recovery.api'
import { getAuditLogs } from '@/services/dashboard.api'

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const qc = useQueryClient()
  const [decision, setDecision] = useState<any>(null)
  const [paymentLink, setPaymentLink] = useState('')
  const [msg, setMsg] = useState('')

  const { data: c, isLoading } = useQuery({ queryKey: ['case', id], queryFn: () => getRecoveryCase(id) })
  const { data: actions = [] } = useQuery({ queryKey: ['actions', id], queryFn: () => getRecoveryActions(id) })
  const { data: logs = [] } = useQuery({ queryKey: ['logs', id], queryFn: () => getAuditLogs(10, 'recovery_case', id) })

  const decideMut = useMutation({
    mutationFn: () => runAIDecision(id),
    onSuccess: d => { setDecision(d); setMsg('') },
    onError: (e: any) => setMsg('AI error: ' + (e.response?.data?.detail?.error?.message ?? e.message)),
  })

  const linkMut = useMutation({
    mutationFn: () => generatePaymentLink(id),
    onSuccess: d => { setPaymentLink(d.payment_link_url ?? d.url ?? d.short_url ?? ''); setMsg('') },
    onError: (e: any) => setMsg('Error: ' + (e.response?.data?.detail?.error?.message ?? e.message)),
  })

  const syncLinkMut = useMutation({
    mutationFn: () => syncPaymentLink(id),
    onSuccess: d => {
      if (d.status === 'recovered') {
        qc.invalidateQueries({ queryKey: ['case', id] })
        qc.invalidateQueries({ queryKey: ['cases'] })
      }
      setMsg(d.status === 'recovered' ? 'Payment confirmed and case recovered.' : `Payment status: ${d.status}`)
    },
    onError: (e: any) => setMsg('Error checking payment: ' + (e.response?.data?.detail?.error?.message ?? e.message)),
  })

  if (isLoading || !c) return (
    <div className="flex h-64 items-center justify-center text-muted-foreground text-sm">Loading…</div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="p-1.5 rounded-lg border hover:bg-muted transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="font-mono text-lg font-bold">{id}</h1>
          <p className="text-xs text-muted-foreground">
            {c.risk_type} · {c.status?.toUpperCase()} · {c.priority}
          </p>
        </div>
      </div>

      {/* 2 key numbers */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border bg-card p-5">
          <p className="text-xs text-muted-foreground mb-1">Amount at Risk</p>
          <p className="text-2xl font-bold text-red-400">₹{(c.amount_at_risk || 0).toLocaleString('en-IN')}</p>
        </div>
        <div className="rounded-xl border bg-card p-5">
          <p className="text-xs text-muted-foreground mb-1">Amount Recovered</p>
          <p className="text-2xl font-bold text-emerald-400">₹{(c.amount_recovered || 0).toLocaleString('en-IN')}</p>
        </div>
      </div>

      {/* Customer context */}
      <div className="rounded-xl border bg-card divide-y">
        {[
          { label: 'Customer ID',  value: c.customer_id },
          { label: 'Invoice ID',   value: c.invoice_id ?? '—' },
          { label: 'Stop Reason',  value: c.stop_reason ?? 'Not stopped' },
          { label: 'Attempts',     value: c.attempt_count ?? 0 },
          { label: 'Risk Score',   value: Math.round((c.risk_score ?? 0) * 100) + '/100' },
        ].map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between px-4 py-3">
            <span className="text-sm text-muted-foreground">{label}</span>
            <span className="text-sm font-medium font-mono">{value}</span>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Recovery Actions</h2>
        <div className="flex gap-3">
          <button
            onClick={() => decideMut.mutate()}
            disabled={decideMut.isPending}
            className="flex items-center gap-2 bg-primary text-primary-foreground rounded-lg px-4 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {decideMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
            Run AI Diagnosis
          </button>
          <button
            onClick={() => linkMut.mutate()}
            disabled={linkMut.isPending}
            className="flex items-center gap-2 border rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
          >
            {linkMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
            Generate Payment Link
          </button>
          <button
            onClick={() => syncLinkMut.mutate()}
            disabled={syncLinkMut.isPending}
            className="border rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
          >
            {syncLinkMut.isPending ? 'Checking…' : 'Check Payment Status'}
          </button>
        </div>

        {msg && <p className="text-sm text-red-400">{msg}</p>}

        {paymentLink && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
            <p className="text-xs text-muted-foreground mb-1">Payment Link</p>
            <a href={paymentLink} target="_blank" rel="noopener noreferrer"
              className="text-sm text-emerald-400 underline break-all">{paymentLink}</a>
          </div>
        )}
      </div>

      {/* AI Decision */}
      {decision && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="text-sm font-semibold">AI Decision</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Strategy',   value: decision.decision?.decision },
              { label: 'Channel',    value: decision.decision?.channel ?? '—' },
              { label: 'Priority',   value: decision.decision?.priority },
              { label: 'Should Stop',value: decision.decision?.should_stop ? 'Yes ⛔' : 'No' },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-muted/30 p-3">
                <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
                <p className="text-sm font-semibold">{String(value ?? '—')}</p>
              </div>
            ))}
          </div>
          {decision.decision?.reason && (
            <p className="text-sm text-muted-foreground bg-muted/20 rounded-lg p-3 leading-relaxed">
              {decision.decision.reason}
            </p>
          )}
        </div>
      )}

      {/* Audit timeline */}
      {logs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Timeline</h2>
          <div className="rounded-xl border bg-card divide-y">
            {logs.map((log: any, i: number) => (
              <div key={i} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{log.action}</p>
                  <p className="text-xs text-muted-foreground">{log.details || log.detail || '—'}</p>
                </div>
                <span className="text-xs text-muted-foreground shrink-0 ml-4">
                  {new Date(log.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
