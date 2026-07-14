import io
import base64
from PIL import Image
import pytesseract
from typing import List
from pipelines.ingestion.base import ExtractedPage
from backend.providers import ChatMessage, NeuroFlowClient, RoutingCriteria


async def extract_image(file_bytes: bytes) -> List[ExtractedPage]:
    pages: List[ExtractedPage] = []
    
    # Load and resize image
    img = Image.open(io.BytesIO(file_bytes))
    max_dim = 1024
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    
    # OCR text
    ocr_text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
    
    # Convert to base64 for LLM
    buffered = io.BytesIO()
    img_format = img.format if img.format else "JPEG"
    img.save(buffered, format=img_format)
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # Get vision LLM description
    client = NeuroFlowClient()
    messages = [
        ChatMessage(
            role="user",
            content=[
                {
                    "type": "text",
                    "text": "Describe this image in detail, including any objects, text, charts, or diagrams. Be thorough and specific."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{img_format.lower()};base64,{img_base64}"}
                }
            ]
        )
    ]
    result = await client.chat(messages, criteria=RoutingCriteria(task_type="rag_generation", require_vision=True))
    
    # Combine description and OCR
    combined_content = f"{result.content}\n\nText found in image: {ocr_text}"
    
    pages.append(ExtractedPage(
        page_number=1,
        content=combined_content,
        content_type="image_description",
        metadata={
            "format": img_format,
            "original_size": (img.width, img.height)
        }
    ))
    
    return pages
