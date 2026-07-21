import ipaddress
import re

import bleach
from fastapi import HTTPException, UploadFile


def strip_html(text: str) -> str:
    return bleach.clean(text, tags=[], strip=True)


def validate_query_text(query: str) -> str:
    cleaned = strip_html(query)
    if len(cleaned) > 5000:
        raise HTTPException(status_code=400, detail="Query text too long (max 5000 chars)")
    return cleaned


def validate_pipeline_name(name: str) -> str:
    cleaned = strip_html(name)
    if len(cleaned) > 100:
        raise HTTPException(status_code=400, detail="Pipeline name too long (max 100 chars)")
    return cleaned


def validate_document_url(url: str) -> str:
    cleaned = strip_html(url)
    if not re.match(r"^https?://", cleaned):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    # Block private IP ranges and localhost
    parsed_host = re.search(r"https?://([^/:]+)", cleaned)
    if parsed_host:
        hostname = parsed_host.group(1)
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback:
                raise HTTPException(status_code=400, detail="URL points to private/loopback IP")
        except ValueError:
            # Not an IP, check if it's localhost
            if hostname in ["localhost", "127.0.0.1", "::1"]:
                raise HTTPException(status_code=400, detail="URL points to localhost")
    
    return cleaned


def validate_file_type(file: UploadFile) -> None:
    # Validate by MIME type first
    allowed_mimes = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "text/csv": ".csv"
    }
    if file.content_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Additional check: ensure filename matches expected extension (basic validation)
    expected_ext = allowed_mimes[file.content_type]
    if not file.filename or not file.filename.endswith(expected_ext):
        raise HTTPException(status_code=400, detail="File extension does not match MIME type")


def validate_file_magic_bytes(file_bytes: bytes, filename: str) -> None:
    expected_magic = {
        ".pdf": b"%PDF",
        ".docx": [
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08"
        ],
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": [
            b"\xff\xd8\xff",
            b"\xff\xd8\xff\xe0\x00\x10JFIF"
        ],
        ".csv": None  # CSV is plain text, no magic bytes
    }
    # Get file extension
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in expected_magic:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    if expected_magic[ext] is None:
        return
    
    # Check magic bytes
    magic = expected_magic[ext]
    if isinstance(magic, bytes):
        if not file_bytes.startswith(magic):
            raise HTTPException(status_code=400, detail="File contents do not match extension")
    elif isinstance(magic, list):
        if not any(file_bytes.startswith(m) for m in magic):
            raise HTTPException(status_code=400, detail="File contents do not match extension")
