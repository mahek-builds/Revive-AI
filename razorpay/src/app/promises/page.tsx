"use client"
import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPromises, createPromise, breakPromise, cancelPromise, getCustomers } from '@/services/misc.api'
import { Loader2, Plus } from 'lucide-react'

const STATUS_COLOR: Record<string, string> = {
  pending: 'text-amber-400', fulfilled: 'text-emerald-400',
  broken: 'text-red-400', cancelled: 'text-zinc-400', overdue: 'text-red-400'
}

export default function PromisesPage() {
  const qc = useQueryClient()
  const [show, setShow] = useState(false)
  const [form, setForm] = useState({ customer_id: '', promised_amount: '', promised_date: '' })
  const [err, setErr] = useState('')

  const { data: promises = [], isLoading } = useQuery({ queryKey: ['promises'], queryFn: () => getPromises(), refetchInterval: 15000 })
  const { data: customers = [] } = useQuery({ queryKey: ['customers'], queryFn: getCustomers })

  const createMut = useMutation({
    mutationFn: () => createPromise({ customer_id: form.customer_id, promised_amount: parseFloat(form.promised_amount), promised_date: form.promised_date }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['promises'] }); setShow(false); setForm({ customer_id: '', promised_amount: '', promised_date: '' }); setErr('') },
    onError: (e: any) => setErr(e.response?.data?.detail?.error?.message ?? e.message),
  })

  const breakMut = useMutation({
    mutationFn: (id: string) => breakPromise(id, 'Not paid'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['promises'] }),
  })

  const cancelMut = useMutation({
    mutationFn: (id: string) => cancelPromise(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['promises'] }),
  })

  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Promises</h1>
          <p className="text-muted-foreground text-sm mt-1">Customer payment commitments tracked by the AI agent</p>
        </div>
        <button onClick={() => setShow(!show)}
          className="flex items-center gap-2 bg-primary text-primary-foreground rounded-lg px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity">
          <Plus className="h-4 w-4" /> New Promise
        </button>
      </div>

      {/* Create form */}
      {show && (
        <div className="rounded-xl border bg-card p-5 space-y-4">
          <h2 className="text-sm font-semibold">Create Promise</h2>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Customer</label>
              <select value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
                className="mt-1 w-full rounded-lg border bg-background text-sm px-3 py-2 focus:outline-none">
                <option value="">Select…</option>
                {customers.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Amount (INR)</label>
              <input type="number" placeholder="1500" value={form.promised_amount}
                onChange={e => setForm(f => ({ ...f, promised_amount: e.target.value }))}
                className="mt-1 w-full rounded-lg border bg-background text-sm px-3 py-2 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Promise Date</label>
              <input type="date" min={today} value={form.promised_date}
                onChange={e => setForm(f => ({ ...f, promised_date: e.target.value }))}
                className="mt-1 w-full rounded-lg border bg-background text-sm px-3 py-2 focus:outline-none" />
            </div>
          </div>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-2">
            <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.customer_id || !form.promised_amount || !form.promised_date}
              className="flex items-center gap-2 bg-primary text-primary-foreground rounded-lg px-4 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50">
              {createMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Save
            </button>
            <button onClick={() => setShow(false)} className="border rounded-lg px-4 py-2 text-sm hover:bg-muted">Cancel</button>
          </div>
        </div>
      )}

      {/* List */}
      <div className="rounded-xl border bg-card overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-muted-foreground text-center py-12">Loading…</p>
        ) : promises.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-12">No promises yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr className="text-xs text-muted-foreground uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Customer</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-center">Promise Date</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {promises.map((p: any) => (
                <tr key={p.id}>
                  <td className="px-4 py-3 font-mono text-xs text-primary">{p.customer_id}</td>
                  <td className="px-4 py-3 text-right font-semibold">₹{(p.promised_amount || 0).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-center text-muted-foreground">
                    {p.promised_date ? new Date(p.promised_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold ${STATUS_COLOR[p.status] ?? 'text-zinc-400'}`}>
                      {p.status?.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.status === 'pending' && (
                      <div className="flex justify-end gap-2">
                        <button onClick={() => breakMut.mutate(p.id)}
                          className="text-xs text-red-400 hover:text-red-300 border border-red-500/30 rounded px-2 py-1">
                          Break
                        </button>
                        <button onClick={() => cancelMut.mutate(p.id)}
                          className="text-xs text-muted-foreground hover:text-foreground border rounded px-2 py-1">
                          Cancel
                        </button>
                      </div>
                    )}
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
