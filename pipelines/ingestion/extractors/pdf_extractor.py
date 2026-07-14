import io
import pypdfium2 as pdfium
import pytesseract
from PIL import Image
import pdfplumber
from typing import List
from pipelines.ingestion.base import ExtractedPage


def extract_pdf(file_bytes: bytes) -> List[ExtractedPage]:
    pages: List[ExtractedPage] = []
    pdf = pdfium.PdfDocument(file_bytes)
    
    # First pass: extract text, check for scanned pages
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        textpage = page.get_textpage()
        text = textpage.get_text_bounded()
        
        metadata = {
            "page_number": page_num + 1,
            "is_scanned": len(text.strip()) < 50
        }
        
        if metadata["is_scanned"]:
            # Rasterize and OCR
            bitmap = page.render(scale=2)
            pil_image = Image.frombytes("RGBA", (bitmap.width, bitmap.height), bitmap.buffer)
            pil_image = pil_image.convert("L")
            ocr_text = pytesseract.image_to_string(pil_image, lang="eng", config="--psm 6")
            pages.append(ExtractedPage(
                page_number=page_num + 1,
                content=ocr_text,
                content_type="text",
                metadata=metadata
            ))
        else:
            pages.append(ExtractedPage(
                page_number=page_num + 1,
                content=text,
                content_type="text",
                metadata=metadata
            ))
    
    # Extract tables with pdfplumber
    with pdfplumber.open(io.BytesIO(file_bytes)) as plumber_pdf:
        for page_num, plumber_page in enumerate(plumber_pdf.pages):
            tables = plumber_page.extract_tables()
            for table_idx, table in enumerate(tables):
                # Convert table to markdown
                md = []
                for row_idx, row in enumerate(table):
                    # Handle None values
                    cleaned_row = [cell or "" for cell in row]
                    md_row = "| " + " | ".join(cleaned_row) + " |"
                    md.append(md_row)
                    if row_idx == 0:
                        md.append("| " + " | ".join(["---"] * len(cleaned_row)) + " |")
                table_md = "\n".join(md)
                pages.append(ExtractedPage(
                    page_number=page_num + 1,
                    content=table_md,
                    content_type="table",
                    metadata={
                        "page_number": page_num + 1,
                        "table_index": table_idx
                    }
                ))
    
    return pages
