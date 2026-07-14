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
        # Since we use docker-entrypoint-initdb.d, migrations are already applied
        # This is just a placeholder for future migrations
        return exists
