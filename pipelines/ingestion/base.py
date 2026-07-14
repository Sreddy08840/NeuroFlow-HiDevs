from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ExtractedPage:
    page_number: int
    content: str
    content_type: str  # "text" | "table" | "image_description"
    metadata: Dict
