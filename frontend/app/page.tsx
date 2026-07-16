import Link from 'next/link'
import { Brain, FileText, GitBranch, MessageSquare } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <main className="container mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-slate-900 mb-4">
            NeuroFlow Dashboard
          </h1>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Manage your RAG pipelines, evaluate performance, and test queries in one place.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Link href="/playground" className="group">
            <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-slate-200">
              <MessageSquare className="w-12 h-12 text-blue-600 mb-4 group-hover:scale-110 transition-transform" />
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Query Playground</h2>
              <p className="text-slate-600">Test queries, compare pipelines, and view evaluations.</p>
            </div>
          </Link>

          <Link href="/pipelines" className="group">
            <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-slate-200">
              <GitBranch className="w-12 h-12 text-purple-600 mb-4 group-hover:scale-110 transition-transform" />
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Pipelines</h2>
              <p className="text-slate-600">Create and manage your RAG pipeline configurations.</p>
            </div>
          </Link>

          <Link href="/evaluations" className="group">
            <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-slate-200">
              <Brain className="w-12 h-12 text-green-600 mb-4 group-hover:scale-110 transition-transform" />
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Evaluations</h2>
              <p className="text-slate-600">View real-time evaluation results and metrics.</p>
            </div>
          </Link>

          <Link href="/documents" className="group">
            <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-slate-200">
              <FileText className="w-12 h-12 text-orange-600 mb-4 group-hover:scale-110 transition-transform" />
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Documents</h2>
              <p className="text-slate-600">Upload and manage your knowledge base documents.</p>
            </div>
          </Link>
        </div>
      </main>
    </div>
  )
}
