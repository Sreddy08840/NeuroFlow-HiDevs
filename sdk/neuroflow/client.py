"""NeuroFlow API client with async support, retries, and streaming."""
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any, List, Union
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
from .models import Document, QueryResult, EvaluationResult, Citation


class NeuroFlowClient:
    """Async client for interacting with the NeuroFlow API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """
        Initialize the NeuroFlow client.

        Args:
            base_url: Base URL of the NeuroFlow API (e.g., "https://api.neuroflow.ai")
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "NeuroFlowClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if not self._client:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    )
    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make an HTTP request with retries on 429 and timeout errors.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to httpx.request

        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        response = await client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response

    async def ingest_file(
        self,
        file_path: Union[str, Path],
        pipeline_id: Optional[str] = None,
        wait: bool = True,
        poll_interval: float = 1.0,
    ) -> Document:
        """
        Upload and ingest a file into NeuroFlow.

        Args:
            file_path: Path to the file to ingest
            pipeline_id: Optional pipeline ID to ingest the file into
            wait: Whether to wait for ingestion to complete
            poll_interval: How often to poll for status if waiting (seconds)

        Returns:
            Document object representing the ingested file
        """
        file_path = Path(file_path)
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {}
            if pipeline_id:
                data["pipeline_id"] = pipeline_id

            response = await self._request("POST", "/ingest/file", files=files, data=data)
            doc_data = response.json()
            doc = Document(**doc_data)

            if not wait:
                return doc

            # Poll until ingestion is complete
            while doc.status not in ("ingested", "failed"):
                await asyncio.sleep(poll_interval)
                doc = await self.get_document(doc.id)

            if doc.status == "failed":
                raise RuntimeError(f"Document ingestion failed: {doc.id}")

            return doc

    async def ingest_url(
        self,
        url: str,
        pipeline_id: Optional[str] = None,
        wait: bool = True,
        poll_interval: float = 1.0,
    ) -> Document:
        """
        Ingest content from a URL into NeuroFlow.

        Args:
            url: URL to ingest content from
            pipeline_id: Optional pipeline ID to ingest into
            wait: Whether to wait for ingestion to complete
            poll_interval: Poll interval if waiting

        Returns:
            Document object representing the ingested content
        """
        payload = {"url": url}
        if pipeline_id:
            payload["pipeline_id"] = pipeline_id

        response = await self._request("POST", "/ingest/url", json=payload)
        doc_data = response.json()
        doc = Document(**doc_data)

        if not wait:
            return doc

        while doc.status not in ("ingested", "failed"):
            await asyncio.sleep(poll_interval)
            doc = await self.get_document(doc.id)

        if doc.status == "failed":
            raise RuntimeError(f"URL ingestion failed: {doc.id}")

        return doc

    async def get_document(self, document_id: str) -> Document:
        """Get details of an ingested document by ID."""
        response = await self._request("GET", f"/documents/{document_id}")
        return Document(**response.json())

    async def query(
        self,
        query: str,
        pipeline_id: str,
        stream: bool = False,
    ) -> Union[QueryResult, AsyncGenerator[str, None]]:
        """
        Run a RAG query against a pipeline.

        Args:
            query: The user's question
            pipeline_id: ID of the pipeline to use
            stream: Whether to stream tokens as they're generated

        Returns:
            If stream=False: QueryResult with full answer and citations
            If stream=True: Async generator yielding token strings
        """
        client = await self._get_client()
        payload = {"query": query, "pipeline_id": pipeline_id, "stream": stream}

        if not stream:
            response = await self._request("POST", "/query", json=payload)
            data = response.json()
            return QueryResult(
                run_id=data["run_id"],
                answer=data["answer"],
                citations=[Citation(**c) for c in data["citations"]],
                sources=data["sources"],
            )

        # Streaming case
        async def token_stream() -> AsyncGenerator[str, None]:
            async with client.stream("POST", "/query", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        yield line

        return token_stream()

    async def get_evaluation(
        self,
        run_id: str,
        wait: bool = True,
        poll_interval: float = 2.0,
    ) -> EvaluationResult:
        """
        Get evaluation results for a query run.

        Args:
            run_id: ID of the query run to evaluate
            wait: Whether to wait for evaluation to complete
            poll_interval: Poll interval if waiting

        Returns:
            EvaluationResult with all metrics
        """
        while True:
            response = await self._request("GET", f"/evaluations/{run_id}")
            data = response.json()

            if not wait or data.get("status") == "completed":
                return EvaluationResult(**data)

            await asyncio.sleep(poll_interval)

    async def list_pipelines(self) -> List[Dict[str, Any]]:
        """List all available pipelines."""
        response = await self._request("GET", "/pipelines")
        return response.json()

    async def create_pipeline(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new pipeline with the given configuration."""
        response = await self._request("POST", "/pipelines", json=config)
        return response.json()
