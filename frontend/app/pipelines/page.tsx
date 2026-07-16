'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Activity, X, ChevronRight, TrendingUp } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import api from '@/utils/api'
import type { Pipeline, PipelineRun } from '@/types'

export default function PipelinesPage() {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null)
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [pipelineConfig, setPipelineConfig] = useState({
    config: {
      name: '',
      description: '',
      retrieval: { top_k: 10, use_rrf: true, use_reranker: true },
      generation: { model_tier: 'standard' as const, temperature: 0.7 },
    },
  })

  const queryClient = useQueryClient()

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: async () => {
      const response = await api.get('/pipelines')
      return response.data as Pipeline[]
    },
  })

  const { data: analytics } = useQuery({
    queryKey: ['pipeline-analytics', selectedPipeline?.id],
    queryFn: async () => {
      if (!selectedPipeline) return null
      const response = await api.get(`/pipelines/${selectedPipeline.id}/analytics`)
      return response.data
    },
    enabled: !!selectedPipeline && showAnalytics,
  })

  const { data: runs } = useQuery({
    queryKey: ['pipeline-runs', selectedPipeline?.id],
    queryFn: async () => {
      if (!selectedPipeline) return []
      const response = await api.get(`/pipelines/${selectedPipeline.id}/runs`)
      return response.data as PipelineRun[]
    },
    enabled: !!selectedPipeline && showAnalytics,
  })

  const createPipelineMutation = useMutation({
    mutationFn: async (data: typeof pipelineConfig) => {
      const response = await api.post('/pipelines', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      setShowCreateModal(false)
      setPipelineConfig({
        config: {
          name: '',
          description: '',
          retrieval: { top_k: 10, use_rrf: true, use_reranker: true },
          generation: { model_tier: 'standard', temperature: 0.7 },
        },
      })
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createPipelineMutation.mutate(pipelineConfig)
  }

  const getScoreColor = (score?: number) => {
    if (!score) return 'text-slate-500'
    if (score >= 0.8) return 'text-green-600'
    if (score >= 0.6) return 'text-yellow-600'
    return 'text-red-600'
  }

  const radarData = analytics?.evaluation_scores
    ? [
        { subject: 'Faithfulness', A: analytics.evaluation_scores.avg_faithfulness || 0, fullMark: 1 },
        { subject: 'Relevance', A: analytics.evaluation_scores.avg_answer_relevance || 0, fullMark: 1 },
        { subject: 'Precision', A: analytics.evaluation_scores.avg_context_precision || 0, fullMark: 1 },
        { subject: 'Recall', A: analytics.evaluation_scores.avg_context_recall || 0, fullMark: 1 },
      ]
    : []

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Pipeline Manager</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          Create Pipeline
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {pipelines?.map((pipeline) => (
          <div key={pipeline.id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">{pipeline.name}</h3>
                <p className="text-sm text-slate-500 mt-1">{pipeline.description}</p>
              </div>
              <button className="text-slate-400 hover:text-red-500">
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-slate-600 space-y-1">
              <p>Total Runs: {pipeline.total_runs || 0}</p>
              <p className={getScoreColor(pipeline.avg_scores?.avg_overall_score)}>
                Avg Score: {pipeline.avg_scores?.avg_overall_score ? `${(pipeline.avg_scores.avg_overall_score * 100).toFixed(0)}%` : 'N/A'}
              </p>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => {
                  setSelectedPipeline(pipeline)
                  setShowAnalytics(true)
                }}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors text-sm"
              >
                <Activity className="w-4 h-4" />
                Analytics
              </button>
            </div>
          </div>
        ))}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-slate-200">
              <h2 className="text-xl font-semibold text-slate-900">Create New Pipeline</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Configuration (JSON)</label>
                <textarea
                  value={JSON.stringify(pipelineConfig.config, null, 2)}
                  onChange={(e) => {
                    try {
                      setPipelineConfig({
                        config: JSON.parse(e.target.value),
                      })
                    } catch {
                      // Ignore invalid JSON
                    }
                  }}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={15}
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createPipelineMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {createPipelineMutation.isPending ? 'Creating...' : 'Create Pipeline'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAnalytics && selectedPipeline && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-slate-200">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">{selectedPipeline.name}</h2>
                <p className="text-sm text-slate-500">Performance Analytics</p>
              </div>
              <button
                onClick={() => setShowAnalytics(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6 space-y-8">
              {/* Latency Chart */}
              {analytics?.latency && (
                <div>
                  <h3 className="text-lg font-medium text-slate-900 mb-4">Latency Percentiles (ms)</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={[
                          { name: 'p50', value: analytics.latency.p50_latency_ms || 0 },
                          { name: 'p95', value: analytics.latency.p95_latency_ms || 0 },
                          { name: 'p99', value: analytics.latency.p99_latency_ms || 0 },
                        ]}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="value" fill="#2563eb" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Evaluation Scores Radar Chart */}
              {radarData.length > 0 && (
                <div>
                  <h3 className="text-lg font-medium text-slate-900 mb-4">Evaluation Metrics</h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="#e2e8f0" />
                        <PolarAngleAxis dataKey="subject" />
                        <PolarRadiusAxis domain={[0, 1]} />
                        <Radar name="Scores" dataKey="A" stroke="#2563eb" fill="#2563eb" fillOpacity={0.3} />
                        <Tooltip formatter={(value: number) => `${(value * 100).toFixed(0)}%`} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Recent Runs */}
              {runs && runs.length > 0 && (
                <div>
                  <h3 className="text-lg font-medium text-slate-900 mb-4">Recent Runs</h3>
                  <div className="space-y-3">
                    {runs.slice(0, 10).map((run) => (
                      <div key={run.id} className="p-4 bg-slate-50 rounded-lg">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-900">{run.query}</p>
                            <p className="text-xs text-slate-500 mt-1">{new Date(run.created_at).toLocaleString()}</p>
                          </div>
                          <div className="ml-4">
                            <span className={`text-sm font-semibold ${getScoreColor(run.overall_score)}`}>
                              {run.overall_score ? `${(run.overall_score * 100).toFixed(0)}%` : 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
