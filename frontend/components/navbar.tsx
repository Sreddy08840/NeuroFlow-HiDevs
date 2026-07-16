'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Brain, FileText, GitBranch, MessageSquare } from 'lucide-react'

const navItems = [
  { href: '/playground', label: 'Playground', icon: MessageSquare },
  { href: '/pipelines', label: 'Pipelines', icon: GitBranch },
  { href: '/evaluations', label: 'Evaluations', icon: Brain },
  { href: '/documents', label: 'Documents', icon: FileText },
]

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <Brain className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-slate-900">NeuroFlow</span>
          </div>
          <div className="flex items-center gap-6">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}
