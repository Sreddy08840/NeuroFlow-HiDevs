-- Enable Row Level Security on all tables
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_pairs ENABLE ROW LEVEL SECURITY;
ALTER TABLE finetune_jobs ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "documents_pipeline_policy" ON documents
USING (pipeline_id = current_setting('app.current_pipeline_id')::uuid);

CREATE POLICY "chunks_pipeline_policy" ON chunks
USING (document_id IN (SELECT id FROM documents WHERE pipeline_id = current_setting('app.current_pipeline_id')::uuid));

CREATE POLICY "pipelines_policy" ON pipelines
USING (id = current_setting('app.current_pipeline_id')::uuid);

CREATE POLICY "pipeline_runs_policy" ON pipeline_runs
USING (pipeline_id = current_setting('app.current_pipeline_id')::uuid);

CREATE POLICY "evaluations_policy" ON evaluations
USING (run_id IN (SELECT id FROM pipeline_runs WHERE pipeline_id = current_setting('app.current_pipeline_id')::uuid));

CREATE POLICY "training_pairs_policy" ON training_pairs
USING (run_id IN (SELECT id FROM pipeline_runs WHERE pipeline_id = current_setting('app.current_pipeline_id')::uuid));

CREATE POLICY "finetune_jobs_policy" ON finetune_jobs
USING (true); -- Admin-only, adjust as needed
