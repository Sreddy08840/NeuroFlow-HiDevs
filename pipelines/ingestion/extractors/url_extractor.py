from urllib.parse import urlparse
import urllib.robotparser
import httpx
import trafilatura
from typing import List
from pipelines.ingestion.base import ExtractedPage


async def extract_url(url: str) -> List[ExtractedPage]:
    pages: List[ExtractedPage] = []
    
    # Check robots.txt
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(f"{base_url}/robots.txt")
        rp.read()
        if not rp.can_fetch("*", url):
            raise PermissionError("URL disallowed by robots.txt")
    except Exception as e:
        # Continue if robots.txt check fails
        pass
    
    # Fetch page
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        html = response.text
    
    # Extract content
    extracted = trafilatura.extract(
        html,
        include_links=True,
        include_tables=True,
        output_format="json"
    )
    
    if extracted:
        import json
        data = json.loads(extracted)
        content = data.get("text", "")
        
        metadata = {
            "title": data.get("title"),
            "author": data.get("author"),
            "canonical_url": data.get("url"),
            "date": data.get("date"),
            "source_url": url
        }
        
        pages.append(ExtractedPage(
            page_number=1,
            content=content,
            content_type="text",
            metadata=metadata
        ))
    
    return pages
