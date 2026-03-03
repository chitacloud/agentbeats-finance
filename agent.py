#!/usr/bin/env python3
"""
AutoPilotAI Finance Agent v3.0 - AgentBeats Sprint 1 Entry
OfficeQA-compatible A2A compliant finance agent for US Treasury Bulletin analysis.

The OfficeQA benchmark evaluates end-to-end grounded reasoning over US Treasury Bulletins
spanning 1939-2025. 697 scanned PDFs, ~89,000 pages. Each question requires:
1. Locating source material in Treasury Bulletins (FRASER archive)
2. Extracting values from tables/figures through document parsing
3. Executing multi-step computations

Supports A2A protocol endpoints:
- POST /a2a/generate (task execution - main eval endpoint)
- GET /.well-known/agent.json (A2A agent card)
- GET /health (health check)
- POST / (A2A JSON-RPC fallback)

Author: Alex Chen (AutoPilotAI) - alexchen.chitacloud.dev
Competition: AgentBeats Phase 2, Sprint 1 - Finance Track
"""

import os
import re
import json
import time
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import urllib.request
import urllib.parse
import urllib.error

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import litellm
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("finance_agent")

AGENT_ID = "autopilotai-finance-v3"
AGENT_VERSION = "3.0.0"
PORT = int(os.environ.get("PORT", 8080))
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# FRASER base URL for Treasury Bulletins
FRASER_BASE = "https://fraser.stlouisfed.org"
FRASER_TITLE_ID = 407  # Treasury Bulletin series ID

# ============================================================
# DOCUMENT FETCHING FROM FRASER ARCHIVE
# ============================================================

_doc_cache: Dict[str, str] = {}

def fetch_fraser_document(url: str) -> Optional[str]:
    """
    Fetch a Treasury Bulletin document from the FRASER archive.
    Returns the text content of the document.
    """
    if url in _doc_cache:
        return _doc_cache[url]

    try:
        log.info(f"Fetching FRASER document: {url}")
        headers = {
            "User-Agent": "AutoPilotAI/3.0 (alex-chen@79661d.inboxapi.ai; AgentBeats Finance Agent)"
        }

        # Try to get the page content first (HTML with document links)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        # Extract PDF link from the page
        pdf_url = extract_pdf_url(content, url)
        if pdf_url:
            text = fetch_pdf_text(pdf_url)
            if text:
                _doc_cache[url] = text
                return text

        # If no PDF, try to extract text from HTML directly
        text = extract_text_from_html(content)
        if text:
            _doc_cache[url] = text
            return text

    except Exception as e:
        log.warning(f"Failed to fetch FRASER document {url}: {e}")

    return None


def extract_pdf_url(html: str, base_url: str) -> Optional[str]:
    """Extract PDF download URL from FRASER page HTML."""
    # Look for PDF download links in FRASER HTML
    patterns = [
        r'href="(/files/docs/[^"]+\.pdf)"',
        r'href="(/download/[^"]+)"',
        r'"pdfUrl"\s*:\s*"([^"]+)"',
        r'href="([^"]+\.pdf)"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            href = m.group(1)
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return f"{FRASER_BASE}{href}"
    return None


def fetch_pdf_text(pdf_url: str) -> Optional[str]:
    """
    Fetch PDF from URL and extract text.
    Uses pdfminer if available, otherwise returns None.
    """
    try:
        import pdfminer.high_level
        import io

        headers = {
            "User-Agent": "AutoPilotAI/3.0 (alex-chen@79661d.inboxapi.ai)"
        }
        req = urllib.request.Request(pdf_url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            pdf_bytes = resp.read()

        text = pdfminer.high_level.extract_text(io.BytesIO(pdf_bytes))
        log.info(f"Extracted {len(text)} chars from PDF: {pdf_url}")
        return text

    except ImportError:
        log.warning("pdfminer not available, cannot extract PDF text")
        return None
    except Exception as e:
        log.warning(f"Failed to extract PDF text from {pdf_url}: {e}")
        return None


def extract_text_from_html(html: str) -> str:
    """Extract plain text from HTML content."""
    # Remove script/style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ============================================================
# LLM-BASED ANSWER EXTRACTION
# ============================================================

def extract_answer_with_llm(question: str, document_text: str, source_url: str = "") -> str:
    """
    Use LLM to extract the answer from document text.
    This is the core reasoning component.
    """
    if not HAS_LITELLM or not LLM_API_KEY:
        return extract_answer_heuristic(question, document_text)

    # Truncate document to fit context (keep most relevant parts)
    max_doc_chars = 60000
    if len(document_text) > max_doc_chars:
        # Try to find the most relevant section
        doc_excerpt = find_relevant_section(question, document_text, max_doc_chars)
    else:
        doc_excerpt = document_text

    prompt = f"""You are analyzing a US Treasury Bulletin document to answer a specific question.

Question: {question}

Document content (from {source_url}):
---
{doc_excerpt}
---

Instructions:
1. Find the specific value or data requested in the question
2. Look carefully in tables, figures, and text for the exact number
3. If computation is needed, show your work step by step
4. Return ONLY the final numeric answer in the exact format expected
5. For dollar amounts: use format like "$1,234.5 million" or "$1.2 billion"
6. For percentages: use format like "5.3%" or "5.3 percent"
7. For plain numbers: use format like "1,234" or "1234"
8. If the answer is not found, return "NOT_FOUND"

Final answer:"""

    try:
        import litellm
        response = litellm.completion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            max_tokens=500,
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        log.info(f"LLM answer: {answer[:100]}")
        return answer
    except Exception as e:
        log.warning(f"LLM call failed: {e}")
        return extract_answer_heuristic(question, document_text)


def find_relevant_section(question: str, text: str, max_chars: int) -> str:
    """Find the most relevant section of a document for a given question."""
    # Extract key terms from question
    # Remove common words
    stop_words = {'what', 'was', 'the', 'of', 'in', 'for', 'a', 'an', 'and', 'or',
                  'how', 'much', 'total', 'is', 'are', 'were', 'did', 'does', 'do',
                  'to', 'from', 'at', 'by', 'with', 'that', 'this', 'which', 'these'}

    words = re.findall(r'\b\w+\b', question.lower())
    key_terms = [w for w in words if w not in stop_words and len(w) > 2]

    # Split text into chunks
    chunk_size = 2000
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append((i, text[i:i+chunk_size]))

    # Score each chunk by keyword matches
    scored = []
    for pos, chunk in chunks:
        score = sum(chunk.lower().count(term) for term in key_terms)
        scored.append((score, pos, chunk))

    # Sort by score, take top chunks
    scored.sort(reverse=True)
    selected = sorted(scored[:max_chars // chunk_size + 1], key=lambda x: x[1])

    return " ... ".join(c for _, _, c in selected)[:max_chars]


def extract_answer_heuristic(question: str, document_text: str) -> str:
    """
    Heuristic-based answer extraction when LLM is not available.
    Looks for numbers near keywords from the question.
    """
    q_lower = question.lower()
    # Extract key numeric patterns from document
    # Find context around numbers with dollar signs
    dollar_pattern = r'\$[\d,]+(?:\.\d+)?\s*(?:million|billion|thousand)?'
    number_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b'

    # Find numbers in the document
    dollars = re.findall(dollar_pattern, document_text, re.IGNORECASE)
    numbers = re.findall(number_pattern, document_text)

    # Return the first significant number found (heuristic fallback)
    if dollars:
        return dollars[0]
    if numbers:
        return numbers[0]

    return "NOT_FOUND"


# ============================================================
# MULTI-STEP REASONING FOR COMPUTATIONS
# ============================================================

def solve_computation(question: str, extracted_values: Dict[str, float]) -> Optional[str]:
    """
    Perform multi-step computations based on extracted values.
    Handles common Treasury Bulletin calculations.
    """
    q_lower = question.lower()

    # Percentage change
    if any(kw in q_lower for kw in ["percent change", "% change", "growth rate", "increase", "decrease"]):
        values = list(extracted_values.values())
        if len(values) >= 2:
            old_val, new_val = sorted(values)[:2]
            if old_val != 0:
                pct = ((new_val - old_val) / abs(old_val)) * 100
                return f"{pct:.1f}%"

    # Ratio
    if any(kw in q_lower for kw in ["ratio", "proportion", "share"]):
        values = list(extracted_values.values())
        if len(values) >= 2:
            ratio = values[0] / values[1]
            return f"{ratio:.2f}"

    # Sum/total
    if any(kw in q_lower for kw in ["total", "sum", "combined"]):
        total = sum(extracted_values.values())
        return f"{total:,.0f}"

    return None


# ============================================================
# MAIN TASK HANDLER
# ============================================================

def process_finance_question(question: str, source_docs: List[str] = None) -> str:
    """
    Main entry point: process a finance question from the OfficeQA benchmark.

    Args:
        question: The question to answer
        source_docs: Optional list of source document URLs from FRASER

    Returns:
        The answer string
    """
    log.info(f"Processing question: {question[:100]}")
    log.info(f"Source docs: {source_docs}")

    # Strategy 1: If source docs provided, fetch and analyze them
    if source_docs:
        for doc_url in source_docs:
            text = fetch_fraser_document(doc_url)
            if text and len(text) > 100:
                answer = extract_answer_with_llm(question, text, doc_url)
                if answer and answer != "NOT_FOUND":
                    log.info(f"Answer from source doc: {answer}")
                    return answer

    # Strategy 2: Search FRASER for relevant Treasury Bulletin
    # Extract date/year from question to find the right bulletin
    year = extract_year_from_question(question)
    month = extract_month_from_question(question)

    if year:
        bulletin_url = find_treasury_bulletin(year, month)
        if bulletin_url:
            text = fetch_fraser_document(bulletin_url)
            if text and len(text) > 100:
                answer = extract_answer_with_llm(question, text, bulletin_url)
                if answer and answer != "NOT_FOUND":
                    return answer

    # Strategy 3: Use LLM with question only (no document - lower quality fallback)
    if HAS_LITELLM and LLM_API_KEY:
        answer = answer_with_llm_only(question)
        if answer:
            return answer

    return "NOT_FOUND"


def find_treasury_bulletin(year: int, month: str = None) -> Optional[str]:
    """
    Construct FRASER URL for a Treasury Bulletin by year/month.
    Format: https://fraser.stlouisfed.org/title/treasury-bulletin-407/{month}-{year}-{id}
    """
    month_map = {
        "january": "january", "february": "february", "march": "march",
        "april": "april", "may": "may", "june": "june",
        "july": "july", "august": "august", "september": "september",
        "october": "october", "november": "november", "december": "december",
    }

    if month:
        month_clean = month.lower().strip()
        if month_clean in month_map:
            # Try to find the specific bulletin
            search_url = f"{FRASER_BASE}/title/treasury-bulletin-407"
            return search_url

    return f"{FRASER_BASE}/title/treasury-bulletin-407"


def extract_year_from_question(question: str) -> Optional[int]:
    """Extract year from question text."""
    # Four-digit year
    years = re.findall(r'\b(1[89][0-9]{2}|20[0-2][0-9])\b', question)
    if years:
        return int(years[0])
    # Two-digit year after apostrophe
    years = re.findall(r"'(\d{2})\b", question)
    if years:
        yr = int(years[0])
        return yr + 1900 if yr >= 39 else yr + 2000
    return None


def extract_month_from_question(question: str) -> Optional[str]:
    """Extract month from question text."""
    months = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december",
              "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    q_lower = question.lower()
    for m in months:
        if m in q_lower:
            return m
    return None


def answer_with_llm_only(question: str) -> Optional[str]:
    """Use LLM knowledge directly for Treasury Bulletin questions."""
    if not HAS_LITELLM or not LLM_API_KEY:
        return None

    prompt = f"""You are an expert on US Treasury Bulletins published by the US Department of the Treasury from 1939 to 2025. 

These bulletins contain detailed financial statistics about US government debt, interest rates, savings bonds, government accounts, and Treasury operations.

Question: {question}

Based on your knowledge of US Treasury Bulletin data and US government financial history, provide the most accurate answer. Return ONLY the numeric answer in the exact format that would appear in the Treasury Bulletin (e.g., dollar amounts in millions, percentages, etc.).

If you cannot determine the answer with confidence, return "NOT_FOUND".

Answer:"""

    try:
        import litellm
        response = litellm.completion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            max_tokens=200,
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        log.info(f"LLM-only answer: {answer[:100]}")
        return answer if answer != "NOT_FOUND" else None
    except Exception as e:
        log.warning(f"LLM-only call failed: {e}")
        return None


# ============================================================
# A2A PROTOCOL HANDLER
# ============================================================

def parse_a2a_task(body: Dict) -> Tuple[str, List[str]]:
    """
    Parse an A2A task message to extract question and source documents.
    Handles various A2A message formats.

    Returns: (question, source_docs)
    """
    question = ""
    source_docs = []

    # Format 1: Direct text message
    if "message" in body:
        msg = body["message"]
        if isinstance(msg, str):
            question = msg
        elif isinstance(msg, dict):
            # A2A message object
            parts = msg.get("parts", [])
            for part in parts:
                if part.get("type") == "text":
                    question += part.get("text", "")
                elif part.get("type") == "data":
                    data = part.get("data", {})
                    if "question" in data:
                        question = data["question"]
                    if "source_docs" in data:
                        source_docs = data["source_docs"]
                    if "source_urls" in data:
                        source_docs = data["source_urls"]

    # Format 2: Direct fields
    if not question and "question" in body:
        question = body["question"]
    if not source_docs and "source_docs" in body:
        source_docs = body["source_docs"]
    if not source_docs and "source_urls" in body:
        source_docs = body["source_urls"]

    # Format 3: JSON-RPC method call
    if "method" in body and "params" in body:
        params = body["params"]
        if isinstance(params, dict):
            question = params.get("question", params.get("message", ""))
            source_docs = params.get("source_docs", params.get("source_urls", []))
        elif isinstance(params, list) and params:
            first_param = params[0]
            if isinstance(first_param, str):
                question = first_param
            elif isinstance(first_param, dict):
                question = first_param.get("question", first_param.get("message", ""))
                source_docs = first_param.get("source_docs", [])

    # Extract FRASER URLs from question if not provided
    if not source_docs:
        fraser_urls = re.findall(r'https://fraser\.stlouisfed\.org/[^\s"\']+', question)
        source_docs = fraser_urls

    return question.strip(), source_docs


def format_a2a_response(answer: str, task_id: str = None) -> Dict:
    """Format response in A2A protocol format."""
    return {
        "id": task_id or str(uuid.uuid4()),
        "status": {
            "state": "completed"
        },
        "artifacts": [
            {
                "parts": [
                    {
                        "type": "text",
                        "text": answer
                    }
                ]
            }
        ],
        "result": answer,
        "answer": answer,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# AGENT CARD (A2A DISCOVERY)
# ============================================================

AGENT_CARD = {
    "name": "AutoPilotAI Finance Agent",
    "description": "OfficeQA-compatible finance agent specializing in US Treasury Bulletin analysis. Answers grounded reasoning questions over Treasury documents spanning 1939-2025 via FRASER archive retrieval and LLM-based extraction.",
    "url": "https://agentbeats-finance.chitacloud.dev",
    "version": AGENT_VERSION,
    "defaultInputModes": ["text/plain", "application/json"],
    "defaultOutputModes": ["text/plain", "application/json"],
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False
    },
    "skills": [
        {
            "id": "treasury-bulletin-qa",
            "name": "Treasury Bulletin QA",
            "description": "Answer questions about US Treasury Bulletins using document retrieval and extraction from FRASER archive",
            "tags": ["finance", "treasury", "document-qa", "grounded-reasoning"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"]
        },
        {
            "id": "financial-computation",
            "name": "Financial Computation",
            "description": "Multi-step financial computations from extracted document values",
            "tags": ["finance", "computation", "arithmetic"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"]
        }
    ]
}


# ============================================================
# FASTAPI SERVER
# ============================================================

if HAS_FASTAPI:
    app = FastAPI(
        title="AutoPilotAI Finance Agent",
        description="OfficeQA-compatible US Treasury Bulletin analysis agent for AgentBeats",
        version=AGENT_VERSION
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
            "llm_available": HAS_LITELLM and bool(LLM_API_KEY),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return JSONResponse(content=AGENT_CARD)

    @app.post("/a2a/generate")
    async def a2a_generate(request: Request):
        """Main A2A evaluation endpoint."""
        try:
            body = await request.json()
            log.info(f"A2A generate request: {str(body)[:200]}")

            question, source_docs = parse_a2a_task(body)

            if not question:
                return JSONResponse(
                    status_code=400,
                    content={"error": "No question found in request"}
                )

            # Process the finance question
            answer = process_finance_question(question, source_docs)

            task_id = body.get("id", str(uuid.uuid4()))
            response = format_a2a_response(answer, task_id)

            log.info(f"Returning answer: {answer[:100]}")
            return JSONResponse(content=response)

        except Exception as e:
            log.error(f"Error in a2a_generate: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )

    @app.post("/")
    async def root_handler(request: Request):
        """JSON-RPC fallback handler."""
        try:
            body = await request.json()
            method = body.get("method", "")
            log.info(f"Root handler: method={method}")

            if method in ["tasks/send", "task/send", "generate", "execute"]:
                return await a2a_generate(request)

            # Default: try to process as a task
            return await a2a_generate(request)

        except Exception as e:
            log.error(f"Root handler error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )

    @app.get("/")
    async def root_get():
        return {
            "name": "AutoPilotAI Finance Agent",
            "version": AGENT_VERSION,
            "benchmark": "OfficeQA - US Treasury Bulletins",
            "endpoints": {
                "task": "POST /a2a/generate",
                "card": "GET /.well-known/agent.json",
                "health": "GET /health"
            }
        }


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AutoPilotAI Finance Agent v3.0")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    parser.add_argument("--card-url", default="", help="Public URL for agent card")
    args = parser.parse_args()

    if args.card_url:
        AGENT_CARD["url"] = args.card_url

    log.info(f"Starting AutoPilotAI Finance Agent v{AGENT_VERSION}")
    log.info(f"Benchmark: OfficeQA - US Treasury Bulletins (1939-2025)")
    log.info(f"LLM available: {HAS_LITELLM and bool(LLM_API_KEY)}")
    log.info(f"Listening on {args.host}:{args.port}")

    if HAS_FASTAPI:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        log.error("FastAPI not available. Cannot start server.")
        import sys
        sys.exit(1)
