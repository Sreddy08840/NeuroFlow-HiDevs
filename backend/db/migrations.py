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
        
        return exists
