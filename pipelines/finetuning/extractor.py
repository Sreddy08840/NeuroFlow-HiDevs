import re
import uuid
import json
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import asyncpg
import tiktoken
from backend.db.pool import get_db_pool
from evaluation.metrics.faithfulness import evaluate_faithfulness

# Regex patterns for PII detection
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")


@dataclass
class TrainingPair:
    pair_id: uuid.UUID
    query: str
    answer: str
    system_prompt: Optional[str]
    quality_score: float
    chunk_contents: List[str]


class Extractor:
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        self.db_pool = db_pool

    async def _get_db_pool(self):
        if self.db_pool is None:
            self.db_pool = await get_db_pool()
        return self.db_pool

    async def _get_faithfulness_score(
        self, query: str, answer: str, context: str
    ) -> float:
        """Get or re-evaluate faithfulness score."""
        return await evaluate_faithfulness(query, answer, context)

    async def _validate_pair(
        self,
        query: str, answer: str, context: str, faithfulness: float
    ) -> tuple[bool, Optional[str]]:
        """Validate training pair against rules."""
        # Check PII check
        if EMAIL_PATTERN.search(query) or PHONE_PATTERN.search(query):
            return False, "Query contains PII"
        
        # Check answer token count
        answer_tokens = tokenizer.encode(answer)
        if len(answer_tokens) < 50 or len(answer_tokens) > 2000:
            return False, "Answer length out of token range"
        
        # Check for citations
        if "[Source " not in answer:
            return False, "Answer missing citations"
        
        # Check faithfulness
        if faithfulness <= 0.8:
            return False, "Faithfulness too low"
        
        return True, None

    async def extract(
        self,
        job_id: uuid.UUID,
        quality_threshold: float = 0.82
    ) -> tuple[List[TrainingPair], List[uuid.UUID], List[Dict[str, Any]]]:
        """Extract and validate training pairs, return valid pairs and their IDs."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT 
                    tp.id AS pair_id,
                    tp.query,
                    tp.assistant_message AS answer,
                    tp.system_prompt,
                    tp.quality_score,
                    pr.retrieved_chunk_ids,
                    pr.user_rating
                FROM training_pairs tp
                JOIN pipeline_runs pr ON tp.run_id = pr.id
                WHERE 
                    tp.quality_score >= $1
                    AND tp.included_in_job IS NULL
                    AND (pr.user_rating >= 4 OR pr.user_rating IS NULL)
            """, quality_threshold)
        
        valid_pairs = []
        valid_pair_ids = []
        valid_jsonls = []
        
        for rec in records:
            pair_id = rec["pair_id"]
            query = rec["query"]
            answer = rec["answer"]
            system_prompt = rec.get("system_prompt") or "You are a precise research assistant. Answer the user's question using ONLY the provided context."
            quality_score = rec["quality_score"]
            retrieved_chunk_ids = rec["retrieved_chunk_ids"] or []
            
            # Get chunk contents from database
            chunk_contents = []
            if retrieved_chunk_ids:
                chunk_records = await conn.fetch("""
                    SELECT content FROM chunks WHERE id = ANY($1)
                    ORDER BY array_position($1::uuid[], id)
                """, retrieved_chunk_ids)
                chunk_contents = [cr["content"] for cr in chunk_records]
            
            context = "\n\n".join(chunk_contents)
            
            # Get or re-evaluate faithfulness
            if quality_score is None:
                quality_score = await self._get_faithfulness_score(query, answer, context)
            
            is_valid, error = await self._validate_pair(query, answer, context, quality_score)
            if is_valid:
                # Format as OpenAI JSONL
                user_content = "[Context]\n" + context + "\n[Question]\n" + query
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": answer}
                ]
                
                valid_pairs.append(TrainingPair(
                    pair_id=pair_id,
                    query=query,
                    answer=answer,
                    system_prompt=system_prompt,
                    quality_score=quality_score,
                    chunk_contents=chunk_contents
                ))
                valid_pair_ids.append(pair_id)
                valid_jsonls.append({"messages": messages})
        
        # Write to file
        jsonl_path = f"training_data/{job_id}.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for line in valid_jsonls:
                f.write(json.dumps(line, ensure_ascii=False))
                f.write("\n")
        
        # Mark pairs as included in job
        if valid_pair_ids:
            await conn.execute("""
                UPDATE training_pairs 
                SET included_in_job = $1 
                WHERE id = ANY($2)
            """, job_id, valid_pair_ids)
        
        return valid_pairs, valid_pair_ids, valid_jsonls

    async def preview(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Preview sample pairs without writing to file or updating database."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT 
                    tp.id AS pair_id,
                    tp.query,
                    tp.assistant_message AS answer,
                    tp.system_prompt,
                    tp.quality_score,
                    pr.retrieved_chunk_ids,
                    pr.user_rating
                FROM training_pairs tp
                JOIN pipeline_runs pr ON tp.run_id = pr.id
                WHERE 
                    tp.included_in_job IS NULL
                    AND (pr.user_rating >=4 OR pr.user_rating IS NULL)
                LIMIT $1
            """, limit)
            
            samples = []
            for rec in records:
                query = rec["query"]
                answer = rec["answer"]
                system_prompt = rec["system_prompt"] or "You are a precise research assistant..."
                retrieved_chunk_ids = rec["retrieved_chunk_ids"] or []
                
                chunk_contents = []
                if retrieved_chunk_ids:
                    chunk_records = await conn.fetch("""
                        SELECT content FROM chunks WHERE id = ANY($1)
                        ORDER BY array_position($1::uuid[], id)
                    """, retrieved_chunk_ids)
                    chunk_contents = [cr["content"] for cr in chunk_records]
                
                context = "\n\n".join(chunk_contents)
                
                user_content = "[Context]\n" + context + "\n[Question]\n" + query
                samples.append({
                    "query": query,
                    "answer": answer,
                    "system_prompt": system_prompt,
                    "chunk_count": len(chunk_contents)
                })
        
        return samples
