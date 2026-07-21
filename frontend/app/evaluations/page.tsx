'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Star, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import api from '@/utils/api'
import type { Evaluation } from '@/types'

export default function EvaluationsPage() {
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [liveEvaluations, setLiveEvaluations] = useState<Evaluation[]>([])

  const { data: evaluations, refetch } = useQuery({
    queryKey: ['evaluations'],
    queryFn: async () => {
      const response = await api.get('/evaluations')
      return response.data as Evaluation[]
    },
  })

  // Combine initial evaluations with live ones
  const allEvaluations = [...liveEvaluations, ...(evaluations || [])]
    .filter((eval1, index, self) => 
      index === self.findIndex(eval2 => eval2.evaluation_id === eval1.evaluation_id)
    )
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  useEffect(() => {
    // SSE connection for live evaluations
    const eventSource = new EventSource(`${api.defaults.baseURL}/evaluations/stream`)
    
    eventSource.onmessage = (event) => {
      const newEval = JSON.parse(event.data) as Evaluation
      setLiveEvaluations(prev => [newEval, ...prev])
    }
    
    eventSource.onerror = () => {
      eventSource.close()
    }

    return () => eventSource.close()
  }, [])

  const filteredEvaluations = allEvaluations.filter((evalItem) => {
    const avgScore = evalItem.overall_score ?? (evalItem.faithfulness + evalItem.answer_relevance + evalItem.context_precision + evalItem.context_recall) / 4
    if (filter === 'high') return avgScore >= 0.85
    if (filter === 'medium') return avgScore >= 0.7 && avgScore < 0.85
    if (filter === 'low') return avgScore < 0.7
    return true
  })

  const getScoreColor = (score: number) => {
    if (score >= 0.85) return 'text-green-600 bg-green-50'
    if (score >= 0.7) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  const formatTime = (date: string) => {
    const d = new Date(date)
    return d.toLocaleString()
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Evaluation Feed</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Filter:</span>
          {(['all', 'high', 'medium', 'low'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {filteredEvaluations.map((evalItem) => {
          const avgScore = evalItem.overall_score ?? (evalItem.faithfulness + evalItem.answer_relevance + evalItem.context_precision + evalItem.context_recall) / 4
          const isExpanded = expandedId === evalItem.evaluation_id
          
          return (
            <div
              key={evalItem.evaluation_id}
              className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 cursor-pointer"
              onClick={() => setExpandedId(isExpanded ? null : evalItem.evaluation_id)}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-slate-500">
                      Query {(evalItem as any).query?.slice(0, 50) || evalItem.run_id}
                      {(evalItem as any).query?.length > 50 ? '...' : ''}
                    </span>
                    <span className="flex items-center gap-1 text-sm text-slate-400">
                      <Clock className="w-4 h-4" />
                      {formatTime(evalItem.created_at)}
                    </span>
                  </div>
                  {evalItem.user_rating !== null && evalItem.user_rating !== undefined && (
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <Star
                          key={star}
                          className={`w-4 h-4 ${
                            star <= (evalItem.user_rating ?? 0)
                              ? 'text-yellow-400 fill-yellow-400'
                              : 'text-slate-200'
                          }`}
                        />
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <div className={`px-4 py-2 rounded-lg font-semibold ${getScoreColor(avgScore)}`}>
                    {Math.round(avgScore * 100)}%
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { name: 'Faithfulness', score: evalItem.faithfulness },
                  { name: 'Answer Relevance', score: evalItem.answer_relevance },
                  { name: 'Context Precision', score: evalItem.context_precision },
                  { name: 'Context Recall', score: evalItem.context_recall },
                ].map((metric) => (
                  <div key={metric.name} className="text-center">
                    <div className={`inline-flex items-center justify-center w-12 h-12 rounded-full mb-2 ${getScoreColor(metric.score)}`}>
                      <span className="text-sm font-bold">{Math.round(metric.score * 100)}</span>
                    </div>
                    <p className="text-sm text-slate-600">{metric.name}</p>
                  </div>
                ))}
              </div>
              
              {isExpanded && (
                <div className="mt-6 pt-6 border-t border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-900 mb-2">Full Query</h3>
                  <p className="text-slate-700 bg-slate-50 p-3 rounded-lg">
                    {(evalItem as any).query || 'No query available'}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
