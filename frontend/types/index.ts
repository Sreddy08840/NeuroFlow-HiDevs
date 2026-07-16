export interface Pipeline {
  id: string
  name: string
  description?: string
  status: string
  current_version: number
  created_at: string
  updated_at: string
  total_runs?: number
  avg_latency_ms?: number
  config?: any
  avg_scores?: {
    avg_faithfulness?: number
    avg_answer_relevance?: number
    avg_context_precision?: number
    avg_context_recall?: number
    avg_overall_score?: number
  }
}

export interface ContextChunk {
  chunk_id: string
  content: string
  metadata: Record<string, any>
  score: number
}

export interface QueryResponse {
  run_id: string
  response: string
  citations: Array<{
    source: string
    chunk_id: string
    document: string
    page?: number
    invalid_citation: boolean
  }>
}

export interface Evaluation {
  evaluation_id: string
  run_id: string
  faithfulness: number
  answer_relevance: number
  context_precision: number
  context_recall: number
  overall_score?: number
  user_rating?: number
  created_at: string
  query?: string
}

export interface Document {
  document_id: string
  filename: string
  source_type: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  chunk_count?: number
  metadata?: Record<string, any>
  created_at: string
}

export interface PipelineRun {
  id: string
  pipeline_id: string
  pipeline_version_id?: string
  query: string
  response: string
  latency_ms?: number
  retrieval_latency_ms?: number
  generation_latency_ms?: number
  created_at: string
  overall_score?: number
}
