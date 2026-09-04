"use client"
import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Activity, Zap, Handshake, FileText, ChevronRight, Bot
} from 'lucide-react'
import { cn } from '@/lib/utils'

const nav = [
  { name: 'Dashboard',    href: '/',          icon: LayoutDashboard },
  { name: 'Cases',        href: '/cases',     icon: Activity },
  { name: 'Simulator',    href: '/simulator', icon: Zap },
  { name: 'Promises',     href: '/promises',  icon: Handshake },
  { name: 'Audit Log',    href: '/audit',     icon: FileText },
]

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname()

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 border-r bg-card flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-5 border-b">
          <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="font-bold text-base tracking-tight">reviveai</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ name, href, icon: Icon }) => {
            const active = href === '/' ? path === '/' : path.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {name}
                {active && <ChevronRight className="h-3 w-3 ml-auto" />}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t">
          <p className="text-xs text-muted-foreground">Track 03 · AI Recovery</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  )
}
