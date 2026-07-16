'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, BookOpen, Activity, ChevronDown, ChevronUp, ThumbsUp, ThumbsDown } from 'lucide-react'
import api from '@/utils/api'
import type { Pipeline } from '@/types'

export default function PlaygroundPage() {
  const [selectedPipeline, setSelectedPipeline] = useState<string>('')
  const [query, setQuery] = useState('')
  const [isComparing, setIsComparing] = useState(false)
  const [showCitations, setShowCitations] = useState(false)
  const [answer, setAnswer] = useState('')
  const [citations, setCitations] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: async () => {
      const response = await api.get('/pipelines')
      return response.data as Pipeline[]
    },
  })

  const submitRating = useMutation({
    mutationFn: async ({ runId, rating }: { runId: string; rating: number }) => {
      await api.patch(`/runs/${runId}/rating`, { rating })
    },
  })

  const handleSubmit = async () => {
    if (!query || !selectedPipeline) return
    setIsLoading(true)
    setAnswer('')
    setCitations([])
    setCurrentRunId(null)

    try {
      const response = await api.post('/query', {
        query,
        pipeline_id: selectedPipeline,
        stream: true,
      })

      const runId = response.data.run_id
      setCurrentRunId(runId)
      const eventSource = new EventSource(`${api.defaults.baseURL}/query/${runId}/stream`)

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'citations') {
          setCitations(data.data)
        } else if (data.type === 'token') {
          setAnswer((prev) => prev + data.data)
        } else if (data.type === 'done') {
          eventSource.close()
          setIsLoading(false)
        }
      }

      eventSource.onerror = () => {
        eventSource.close()
        setIsLoading(false)
      }
    } catch (error) {
      console.error('Error querying:', error)
      setIsLoading(false)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-slate-900 mb-8">Query Playground</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-4 mb-4">
              <select
                value={selectedPipeline}
                onChange={(e) => setSelectedPipeline(e.target.value)}
                className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Pipeline</option>
                {pipelines?.map((pipeline) => (
                  <option key={pipeline.id} value={pipeline.id}>
                    {pipeline.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setIsComparing(!isComparing)}
                className={`px-4 py-2 rounded-lg border transition-colors ${
                  isComparing
                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                    : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                }`}
              >
                Compare Mode
              </button>
            </div>

            <div className="flex gap-4">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter your query..."
                className="flex-1 px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={4}
              />
              <button
                onClick={handleSubmit}
                disabled={isLoading || !query || !selectedPipeline}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <Send className="w-5 h-5" />
                {isLoading ? 'Loading...' : 'Send'}
              </button>
            </div>
          </div>

          {answer && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-slate-900">Answer</h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => currentRunId && submitRating.mutate({ runId: currentRunId, rating: 5 })}
                    disabled={!currentRunId || submitRating.isPending}
                    className="p-2 hover:bg-green-50 text-slate-400 hover:text-green-600 rounded-lg transition-colors"
                  >
                    <ThumbsUp className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => currentRunId && submitRating.mutate({ runId: currentRunId, rating: 1 })}
                    disabled={!currentRunId || submitRating.isPending}
                    className="p-2 hover:bg-red-50 text-slate-400 hover:text-red-600 rounded-lg transition-colors"
                  >
                    <ThumbsDown className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => setShowCitations(!showCitations)}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    <BookOpen className="w-4 h-4" />
                    Citations
                    {showCitations ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{answer}</p>
              {showCitations && citations.length > 0 && (
                <div className="mt-6 pt-6 border-t border-slate-200">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Sources</h3>
                  <div className="space-y-4">
                    {citations.map((citation, idx) => (
                      <div key={idx} className="p-4 bg-slate-50 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-slate-600">
                            {citation.document} (Page {citation.page || 'N/A'})
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-blue-600" />
              <h2 className="text-xl font-semibold text-slate-900">Evaluation Scores</h2>
            </div>
            {answer ? (
              <div className="space-y-4">
                {/* We'll update this when we implement evaluations endpoint */}
                <p className="text-slate-500 text-center py-8">Evaluation scores coming soon...</p>
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">Send a query to see scores</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
