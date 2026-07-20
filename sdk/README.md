# NeuroFlow SDK

The official Python SDK for NeuroFlow, the enterprise RAG platform.

## Quickstart

Install the SDK:
```bash
pip install ./sdk
```

Use it in your code:
```python
import asyncio
from neuroflow import NeuroFlowClient

async def main():
    async with NeuroFlowClient(base_url="http://localhost:8000", api_key="your-key") as client:
        # List pipelines
        pipelines = await client.list_pipelines()
        pipeline_id = pipelines[0]["id"]

        # Ingest a file
        doc = await client.ingest_file("path/to/doc.pdf", pipeline_id=pipeline_id)
        print(f"Ingested document: {doc.filename}")

        # Run a query with streaming
        async for token in await client.query("What is RAG?", pipeline_id=pipeline_id, stream=True):
            print(token, end="", flush=True)

asyncio.run(main())
```
