import re
import logging
from typing import List, Dict, Any


logger = logging.getLogger(__name__)

SECRET_PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "generic_api_key": r"['\"]?(?:api|secret|token|key|password)['\"]?\s*[:=]\s*['\"][A-Za-z0-9/+]{20,}['\"]",
    "private_key_pem": r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP|CERTIFICATE) PRIVATE KEY-----",
    "jwt_token": r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
}

def detect_secrets(text: str) -> List[Dict[str, str]]:
    detected = []
    for name, pattern in SECRET_PATTERNS.items():
        for match in re.finditer(pattern, text):
            detected.append({
                "pattern_type": name,
                "match": match.group(0),
                "start": match.start(),
                "end": match.end()
            })
    return detected


def redact_secrets(text: str, detected: List[Dict[str, str]]) -> Tuple[str, List[str]]:
    if not detected:
        return text, []
    
    # Sort matches by position descending to avoid overlapping issues
    sorted_matches = sorted(detected, key=lambda x: -x["start"])
    redacted_patterns = []
    
    for match in sorted_matches:
        text = text[:match["start"]] + "[REDACTED]" + text[match["end"]:]
        redacted_patterns.append(match["pattern_type"])
    
    return text, list(set(redacted_patterns))
