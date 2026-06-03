"""
LogSentry - Log enrichment and metadata processing.
"""

import hashlib
import re
import logging
from datetime import datetime

logger = logging.getLogger("enricher")

# Patterns for extracting structured data from log messages
PATTERNS = {
    "status_code": re.compile(r'\b(status[_\s]?(?:code)?|HTTP)[:\s=]*(\d{3})\b', re.IGNORECASE),
    "duration": re.compile(r'\b(?:duration|elapsed|took|time|latency|response_time)[:\s=]*(\d+(?:\.\d+)?)\s*(?:ms|milliseconds|s|seconds)?\b', re.IGNORECASE),
    "ip_address": re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'),
    "url_path": re.compile(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]*)', re.IGNORECASE),
    "exception": re.compile(r'(?:Exception|Error|Traceback|Caused by)[:\s]+(.+?)(?:\n|$)', re.IGNORECASE),
    "user_id": re.compile(r'\buser[_\s]?(?:id)?[:\s=]*([a-zA-Z0-9_-]+)\b', re.IGNORECASE),
}

# Stack trace indicators
STACK_TRACE_INDICATORS = [
    "Traceback (most recent call last)",
    "at ",
    "Exception in thread",
    "Caused by:",
    "    at ",
    "File \"",
]


def enrich_log_entry(entry: dict) -> dict:
    """
    Enrich a log entry with extracted metadata.
    
    Adds processing timestamp, extracts structured data from the message,
    and normalizes fields.
    """
    enriched = dict(entry)
    
    # Ensure timestamp
    if not enriched.get("timestamp"):
        enriched["timestamp"] = datetime.utcnow().isoformat()
    
    # Ensure metadata dict exists
    if not enriched.get("metadata"):
        enriched["metadata"] = {}
    
    message = enriched.get("message", "")
    
    # Extract structured data from message
    extracted = extract_structured_data(message)
    if extracted:
        enriched["metadata"]["extracted"] = extracted
    
    # Check for stack traces
    stack_info = extract_stack_trace(message)
    if stack_info:
        enriched["metadata"]["stack_trace"] = stack_info
    
    # Add processing metadata
    enriched["metadata"]["processed_at"] = datetime.utcnow().isoformat()
    
    return enriched


def generate_error_fingerprint(message: str, service_name: str) -> str:
    """
    Generate a fingerprint for error grouping.
    
    Normalizes the error message by removing variable parts (IDs, timestamps, 
    numbers) and creates a hash for deduplication.
    """
    # Normalize the message
    normalized = message.strip()
    
    # Remove UUIDs
    normalized = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '<UUID>', normalized, flags=re.IGNORECASE
    )
    
    # Remove numeric IDs
    normalized = re.sub(r'\b\d{4,}\b', '<ID>', normalized)
    
    # Remove IP addresses
    normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', normalized)
    
    # Remove timestamps
    normalized = re.sub(
        r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?',
        '<TS>', normalized
    )
    
    # Remove hex strings
    normalized = re.sub(r'\b[0-9a-f]{8,}\b', '<HEX>', normalized, flags=re.IGNORECASE)
    
    # Create fingerprint
    fingerprint_input = f"{service_name}:{normalized[:500]}"
    return hashlib.md5(fingerprint_input.encode()).hexdigest()[:16]


def extract_structured_data(message: str) -> dict:
    """Extract structured data from log message using regex patterns."""
    extracted = {}
    
    for name, pattern in PATTERNS.items():
        match = pattern.search(message)
        if match:
            if name == "status_code":
                extracted["status_code"] = int(match.group(2))
            elif name == "duration":
                extracted["duration_ms"] = float(match.group(1))
            elif name == "ip_address":
                extracted["ip_address"] = match.group(1)
            elif name == "url_path":
                extracted["url_path"] = match.group(1)
            elif name == "exception":
                extracted["exception_type"] = match.group(1).strip()[:200]
            elif name == "user_id":
                extracted["user_id"] = match.group(1)
    
    return extracted


def extract_stack_trace(message: str) -> dict | None:
    """Detect and parse stack traces from log messages."""
    has_stack_trace = any(indicator in message for indicator in STACK_TRACE_INDICATORS)
    
    if not has_stack_trace:
        return None
    
    lines = message.split("\n")
    
    # Find exception type
    exception_type = None
    exception_message = None
    
    for line in lines:
        # Python exception
        py_match = re.match(r'^(\w+(?:\.\w+)*(?:Error|Exception|Warning)):\s*(.+)?$', line.strip())
        if py_match:
            exception_type = py_match.group(1)
            exception_message = py_match.group(2)
            break
        
        # Java exception
        java_match = re.match(r'^(?:Caused by:\s*)?(\w+(?:\.\w+)*(?:Exception|Error)):\s*(.+)?$', line.strip())
        if java_match:
            exception_type = java_match.group(1)
            exception_message = java_match.group(2)
            break
    
    return {
        "has_stack_trace": True,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "stack_depth": sum(1 for line in lines if line.strip().startswith(("at ", "File ", "    at "))),
    }
