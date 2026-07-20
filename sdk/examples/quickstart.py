"""Quickstart example for NeuroFlow SDK."""
import asyncio
import os
from neuroflow import NeuroFlowClient


async def main():
    # Configure client
    base_url = os.getenv("NEUROFLOW_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("NEUROFLOW_API_KEY", "your-api-key")

    async with NeuroFlowClient(base_url=base_url, api_key=api_key) as client:
        # List pipelines
        print("Listing pipelines...")
        pipelines = await client.list_pipelines()
        if not pipelines:
            print("No pipelines found. Create one first!")
            return

        pipeline_id = pipelines[0]["id"]
        print(f"Using pipeline: {pipeline_id}")

        # Ingest a test file (create a simple text file if not exists)
        test_file = "test_doc.txt"
        if not os.path.exists(test_file):
            with open(test_file, "w") as f:
                f.write(
                    "NeuroFlow is an enterprise RAG platform. "
                    "It supports document ingestion, querying, and evaluation."
                )

        print(f"Ingesting file: {test_file}")
        doc = await client.ingest_file(test_file, pipeline_id=pipeline_id)
        print(f"Ingested document ID: {doc.id}")

        # Run a query with streaming
        query = "What is NeuroFlow?"
        print(f"\nRunning query: {query}")
        stream = await client.query(query, pipeline_id=pipeline_id, stream=True)
        async for token in stream:
            print(token, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
