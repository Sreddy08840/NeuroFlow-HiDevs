from db.pool import get_db_pool


async def check_and_apply_migrations():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if schema exists by checking for 'documents' table
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'documents'
            )
        """)
        
        # Migration: Add metadata column to pipeline_runs if not exists
        metadata_col_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'pipeline_runs' AND column_name = 'metadata'
            )
        """)
        if not metadata_col_exists:
            await conn.execute("""
                ALTER TABLE pipeline_runs 
                ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'
            """)
        
        # Migration: Update pipelines table and add pipeline_versions
        # First, check if pipeline_versions exists
        pv_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'pipeline_versions'
            )
        """)
        if not pv_exists:
            # First, alter existing pipelines table to add new columns
            await conn.execute("""
                ALTER TABLE pipelines 
                ADD COLUMN IF NOT EXISTS description TEXT,
                ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active',
                ADD COLUMN IF NOT EXISTS current_version INT NOT NULL DEFAULT 1,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                DROP COLUMN IF EXISTS config
            """)
            
            # Create pipeline_versions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_versions (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    pipeline_id UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
                    version INT NOT NULL,
                    config JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(pipeline_id, version)
                )
            """)
            
            # Add pipeline_version_id to pipeline_runs
            await conn.execute("""
                ALTER TABLE pipeline_runs 
                ADD COLUMN IF NOT EXISTS pipeline_version_id UUID REFERENCES pipeline_versions(id),
                ADD COLUMN IF NOT EXISTS retrieval_latency_ms INT,
                ADD COLUMN IF NOT EXISTS generation_latency_ms INT
            """)
        
        return exists
