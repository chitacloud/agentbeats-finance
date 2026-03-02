#!/usr/bin/env python3
"""
AutoPilotAI Finance Agent v3.0 - AgentBeats Sprint 1 Entry
FinanceBench-compatible A2A compliant autonomous finance agent.

Supports the FinanceBench evaluation benchmark:
- 537 questions on SEC 10-K/10-Q/earnings reports
- Categories: quantitative retrieval, numerical reasoning, GAAP adjustments,
  beat-or-miss, trend analysis, financial modeling, market analysis

A2A Protocol: A2AStarletteApplication (google-a2a compatible)
Author: Alex Chen (AutoPilotAI) - alexchen.chitacloud.dev
Competition: AgentBeats Phase 2, Sprint 1 - Finance Track
"""

import os
import json
import time
import uuid
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, AsyncIterable, Union

import urllib.request
import urllib.parse
import urllib.error

# A2A SDK imports
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Message,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Artifact,
    Part,
    TextPart,
    UnsupportedOperationError,
)

# Try LiteLLM for LLM-powered answers
try:
    from litellm import completion
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False

# Try yfinance for live market data
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("finance_agent")

AGENT_VERSION = "3.0.0"

# LLM configuration from environment
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")


# ============================================================
# FINANCIAL KNOWLEDGE BASE
# ============================================================

FINANCIAL_FORMULAS = {
    "pe_ratio": lambda price, eps: round(price / eps, 2) if eps and eps != 0 else None,
    "pb_ratio": lambda price, bvps: round(price / bvps, 2) if bvps and bvps != 0 else None,
    "cagr": lambda start, end, years: round(((end / start) ** (1 / years) - 1) * 100, 2),
    "roi": lambda gain, cost: round((gain / cost) * 100, 2),
    "eps": lambda net_income, shares: round(net_income / shares, 2) if shares and shares != 0 else None,
    "debt_to_equity": lambda debt, equity: round(debt / equity, 2) if equity and equity != 0 else None,
    "current_ratio": lambda ca, cl: round(ca / cl, 2) if cl and cl != 0 else None,
    "gross_margin": lambda revenue, cogs: round((revenue - cogs) / revenue * 100, 2) if revenue else None,
    "operating_margin": lambda oi, rev: round(oi / rev * 100, 2) if rev else None,
    "net_margin": lambda ni, rev: round(ni / rev * 100, 2) if rev else None,
    "revenue_growth": lambda curr, prev: round((curr - prev) / prev * 100, 2) if prev else None,
    "sharpe": lambda ret, rf, std: round((ret - rf) / std, 2) if std and std != 0 else None,
}

TICKER_MAP = {
    "Netflix": "NFLX", "Apple": "AAPL", "Microsoft": "MSFT", "Google": "GOOGL",
    "Alphabet": "GOOGL", "Amazon": "AMZN", "Tesla": "TSLA", "Meta": "META",
    "Facebook": "META", "NVIDIA": "NVDA", "AMD": "AMD", "Intel": "INTC",
    "JPMorgan": "JPM", "Goldman Sachs": "GS", "Morgan Stanley": "MS",
    "Bank of America": "BAC", "Citigroup": "C", "Wells Fargo": "WFC",
    "Walmart": "WMT", "Target": "TGT", "Home Depot": "HD", "Costco": "COST",
    "Johnson & Johnson": "JNJ", "Pfizer": "PFE", "Moderna": "MRNA",
    "Exxon": "XOM", "Chevron": "CVX", "Boeing": "BA",
    "TJX": "TJX", "TJX Companies": "TJX", "BBSI": "BBSI",
    "Palantir": "PLTR", "Snowflake": "SNOW", "Datadog": "DDOG",
    "CrowdStrike": "CRWD", "Palo Alto": "PANW",
    "Berkshire Hathaway": "BRK-B", "Disney": "DIS",
    "PayPal": "PYPL", "Visa": "V", "Mastercard": "MA",
    "US Steel": "X", "Lockheed Martin": "LMT",
}


# ============================================================
# SEC EDGAR DATA FETCHING
# ============================================================

def fetch_sec_filing(company: str, form_type: str = "10-K") -> Optional[Dict]:
    """Fetch company SEC filing data."""
    try:
        search_url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{urllib.parse.quote(company)}%22"
            f"&dateRange=custom&startdt=2022-01-01&enddt=2025-12-31&forms={form_type}"
        )
        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "AutoPilotAI alex-chen@79661d.inboxapi.ai"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                return {
                    "source": "SEC EDGAR",
                    "company": company,
                    "form_type": form_type,
                    "filings_found": len(hits),
                    "latest": hits[0].get("_source", {}) if hits else None
                }
    except Exception as e:
        log.debug(f"SEC EDGAR fetch failed: {e}")
    return None


def fetch_yfinance_data(ticker: str) -> Optional[Dict]:
    """Fetch financial data via yfinance."""
    if not HAS_YFINANCE:
        return None
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            return None
        return {
            "ticker": ticker,
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "price": info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "revenue_ttm": info.get("totalRevenue"),
            "net_income_ttm": info.get("netIncomeToCommon"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "book_value": info.get("bookValue"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_value": info.get("enterpriseValue"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception as e:
        log.debug(f"yfinance fetch failed for {ticker}: {e}")
    return None


def extract_ticker(text: str) -> Optional[str]:
    """Extract stock ticker from text."""
    # Explicit NASDAQ/NYSE format
    m = re.search(r'(?:NASDAQ|NYSE):\s*([A-Z]{1,5})\b', text)
    if m:
        return m.group(1)
    # Company name lookup
    for name, ticker in TICKER_MAP.items():
        if name.lower() in text.lower() and ticker:
            return ticker
    # Bare ticker (ALL CAPS, 1-5 chars)
    m = re.search(r'\b([A-Z]{1,5})\b', text)
    if m:
        candidate = m.group(1)
        # Skip common words
        if candidate not in {"SEC", "GAAP", "USA", "CEO", "CFO", "Q1", "Q2", "Q3", "Q4",
                              "YOY", "YTD", "TTM", "EPS", "PE", "ROI", "AI", "ML",
                              "ARPU", "CAGR", "BPS", "MDA", "IPO", "FY", "EBIT", "EBITDA"}:
            return candidate
    return None


# ============================================================
# DIRECT CALCULATION ENGINE
# ============================================================

def try_direct_calculation(question: str) -> Optional[str]:
    """Handle explicit numerical calculation questions directly."""
    q = question.lower()

    # CAGR
    if re.search(r'cagr|compound annual growth', q):
        nums = re.findall(r'\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|thousand)?', question)
        years_m = re.search(r'(\d+)\s+years?', q)
        if len(nums) >= 2 and years_m:
            try:
                start = float(nums[0].replace(',', ''))
                end = float(nums[1].replace(',', ''))
                years = int(years_m.group(1))
                # Handle billion/million
                if 'billion' in question[:question.lower().find(nums[1])].lower():
                    start *= 1e9
                    end *= 1e9
                cagr = FINANCIAL_FORMULAS["cagr"](start, end, years)
                return f"The CAGR is {cagr}% over {years} years (from {nums[0]} to {nums[1]})."
            except Exception:
                pass

    # P/E ratio
    if re.search(r'p/?e\s+ratio|price.to.earnings', q):
        price_m = re.search(r'price.{0,20}\$?([\d.]+)', q)
        eps_m = re.search(r'(?:eps|earnings per share).{0,20}\$?([\d.]+)', q)
        if price_m and eps_m:
            try:
                pe = FINANCIAL_FORMULAS["pe_ratio"](float(price_m.group(1)), float(eps_m.group(1)))
                if pe:
                    return f"P/E ratio = {pe}x (Price ${price_m.group(1)} / EPS ${eps_m.group(1)})"
            except Exception:
                pass

    # Gross margin
    if re.search(r'gross margin', q):
        nums = re.findall(r'\$?([\d,]+(?:\.\d+)?)', question)
        if len(nums) >= 2:
            try:
                revenue = float(nums[0].replace(',', ''))
                cogs = float(nums[1].replace(',', ''))
                if revenue > cogs:
                    gm = FINANCIAL_FORMULAS["gross_margin"](revenue, cogs)
                    return f"Gross margin = {gm}% (Revenue: {nums[0]}, COGS: {nums[1]})"
            except Exception:
                pass

    # Beat or miss with BPS
    if re.search(r'beat|miss|bps', q):
        nums = re.findall(r'([\d.]+)\s*(?:%|bps?|basis points?)', question, re.IGNORECASE)
        if len(nums) >= 2:
            try:
                actual = float(nums[0])
                guidance = float(nums[1])
                diff = actual - guidance
                unit = "bps" if re.search(r'bps|basis', q) else "%"
                direction = "beat" if diff > 0 else "missed"
                return f"The result {direction} guidance by {abs(diff):.1f}{unit} (actual: {actual}, guidance: {guidance})"
            except Exception:
                pass

    return None


# ============================================================
# LLM-POWERED ANSWER ENGINE
# ============================================================

def build_llm_prompt(question: str, context: str = "", yf_data: Optional[Dict] = None) -> str:
    """Build a prompt for the LLM to answer a finance question."""
    system_context = """You are an expert financial analyst with deep knowledge of:
- SEC filings (10-K, 10-Q, 8-K, proxy statements)
- Financial statements (income statement, balance sheet, cash flow)
- Financial ratios and metrics (P/E, CAGR, margins, ROI, EPS, debt ratios)
- GAAP vs non-GAAP adjustments
- Earnings beats/misses and guidance analysis
- Industry trends and market analysis
- FinanceBench benchmark questions

Answer the question concisely and accurately. If the question asks for a specific number,
provide that number with proper units. If asking about a trend, describe it clearly.
Focus on precision and factual accuracy."""

    market_context = ""
    if yf_data:
        fields = []
        if yf_data.get("company_name"):
            fields.append(f"Company: {yf_data['company_name']} ({yf_data.get('ticker', '')})")
        if yf_data.get("revenue_ttm"):
            fields.append(f"Revenue (TTM): ${yf_data['revenue_ttm']/1e9:.2f}B")
        if yf_data.get("net_income_ttm"):
            fields.append(f"Net Income (TTM): ${yf_data['net_income_ttm']/1e9:.2f}B")
        if yf_data.get("gross_margins"):
            fields.append(f"Gross Margin: {yf_data['gross_margins']*100:.1f}%")
        if yf_data.get("operating_margins"):
            fields.append(f"Operating Margin: {yf_data['operating_margins']*100:.1f}%")
        if yf_data.get("pe_ratio"):
            fields.append(f"P/E Ratio: {yf_data['pe_ratio']:.1f}x")
        if yf_data.get("market_cap"):
            fields.append(f"Market Cap: ${yf_data['market_cap']/1e9:.1f}B")
        if yf_data.get("revenue_growth"):
            fields.append(f"Revenue Growth (YoY): {yf_data['revenue_growth']*100:.1f}%")
        if fields:
            market_context = "\n\nLive Market Data:\n" + "\n".join(fields)

    filing_context = f"\n\nFiling Context:\n{context}" if context else ""

    return f"""{system_context}{market_context}{filing_context}

Question: {question}

Answer:"""


def get_llm_answer(question: str, context: str = "", yf_data: Optional[Dict] = None) -> str:
    """Get LLM-powered answer for a financial question."""
    if not HAS_LITELLM or not LLM_API_KEY:
        return None

    try:
        prompt = build_llm_prompt(question, context, yf_data)

        kwargs = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.1,
        }

        if LLM_API_KEY:
            kwargs["api_key"] = LLM_API_KEY
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
            kwargs["api_key"] = LLM_API_KEY or "not-needed"

        response = completion(**kwargs)
        answer = response.choices[0].message.content.strip()
        log.info(f"LLM answer generated ({len(answer)} chars)")
        return answer
    except Exception as e:
        log.warning(f"LLM generation failed: {e}")
        return None


# ============================================================
# RULE-BASED FALLBACK ENGINE
# ============================================================

def get_rule_based_answer(question: str, yf_data: Optional[Dict] = None) -> str:
    """Rule-based financial reasoning as fallback."""
    q = question.lower()
    ticker = extract_ticker(question)

    # ARPU questions
    if "arpu" in q or "average revenue per user" in q:
        company = yf_data.get("company_name", ticker or "the company") if yf_data else (ticker or "the company")
        return (
            f"{company} ARPU trends reflect pricing strategy, subscriber mix shifts, "
            "geographic expansion into lower-ARPU markets, and product tier evolution. "
            "Growth in ad-supported tiers typically pressures ARPU while expanding TAM."
        )

    # Guidance/Outlook
    if re.search(r'guidance|outlook|forecast|projected', q):
        if yf_data and yf_data.get("revenue_ttm"):
            rev = yf_data["revenue_ttm"]
            qrev = rev / 4
            company = yf_data.get("company_name", ticker)
            return (
                f"{company} quarterly revenue run rate: ~${qrev/1e9:.1f}B based on TTM revenue of ${rev/1e9:.1f}B. "
                "Management guidance reflects macro conditions, pipeline visibility, and execution confidence."
            )
        return (
            "Company guidance typically reflects management's view of macro conditions, "
            "competitive dynamics, and pipeline visibility over the next 1-4 quarters."
        )

    # Beat/Miss questions
    if re.search(r'beat|miss|exceeded|fell short|outperform|underperform', q):
        return (
            "To determine a beat or miss, compare actual reported results against "
            "consensus analyst estimates or management guidance midpoint. "
            "A beat occurs when actuals exceed estimates; a miss when they fall short."
        )

    # Trend analysis
    if re.search(r'trend|changed|growth rate|decline|increase|year.over.year|yoy|quarter.over.quarter|qoq', q):
        if yf_data:
            parts = []
            rg = yf_data.get("revenue_growth")
            eg = yf_data.get("earnings_growth")
            company = yf_data.get("company_name", ticker)
            if rg:
                parts.append(f"Revenue growth (YoY): {rg*100:.1f}%")
            if eg:
                parts.append(f"Earnings growth (YoY): {eg*100:.1f}%")
            if parts:
                return f"{company}: {' | '.join(parts)}"

    # Risk factors
    if re.search(r'risk factor|risk categor|1a|section 1', q):
        return (
            "SEC 10-K Section 1A risk factors typically span: Market/Competition risks, "
            "Operational risks, Financial/Liquidity risks, Regulatory/Legal risks, "
            "Cybersecurity risks, Supply Chain risks, Macroeconomic risks, "
            "Technology/Innovation risks, Human Capital risks, and Environmental/ESG risks."
        )

    # M&A questions
    if re.search(r'merger|acquisition|acquir|takeover|deal|transaction', q):
        companies = [name for name in TICKER_MAP if name.lower() in q]
        if len(companies) >= 2:
            return (
                f"The {companies[0]}/{companies[1]} transaction involves strategic rationale, "
                "synergy realization, regulatory review, and integration execution. "
                "Acquirers typically pay 20-30% control premium with integration costs "
                "offsetting near-term synergies."
            )

    # Financial metrics from yfinance
    if yf_data:
        metrics = []
        company = yf_data.get("company_name", ticker or "Company")
        if yf_data.get("revenue_ttm"):
            metrics.append(f"Revenue (TTM): ${yf_data['revenue_ttm']/1e9:.2f}B")
        if yf_data.get("gross_margins"):
            metrics.append(f"Gross margin: {yf_data['gross_margins']*100:.1f}%")
        if yf_data.get("pe_ratio"):
            metrics.append(f"P/E: {yf_data['pe_ratio']:.1f}x")
        if yf_data.get("market_cap"):
            metrics.append(f"Market cap: ${yf_data['market_cap']/1e9:.1f}B")
        if metrics:
            return f"{company} ({ticker}): {' | '.join(metrics)}."

    # Generic financial analysis
    return (
        "This financial question requires analysis of SEC filings and earnings reports. "
        "Key financial metrics include revenue growth, margin trajectory, EPS trends, "
        "free cash flow generation, and capital allocation strategy. "
        "For precise figures, refer to the company's latest 10-K or earnings release."
    )


# ============================================================
# MAIN ANSWER FUNCTION
# ============================================================

def answer_finance_question(question: str, rubric: Optional[List] = None) -> str:
    """
    Main function to answer a finance question.
    Strategy: Direct calc -> LLM with context -> Rule-based fallback
    """
    log.info(f"Answering: {question[:120]}...")

    # Step 1: Try direct calculation
    calc_answer = try_direct_calculation(question)
    if calc_answer:
        log.info("Used direct calculation engine")
        return calc_answer

    # Step 2: Fetch live market data if ticker found
    ticker = extract_ticker(question)
    yf_data = None
    if ticker:
        yf_data = fetch_yfinance_data(ticker)
        if yf_data:
            log.info(f"Fetched yfinance data for {ticker}: {yf_data.get('company_name', ticker)}")

    # Step 3: Try LLM if available
    if HAS_LITELLM and LLM_API_KEY:
        # Build context from yfinance if available
        context = ""
        if yf_data:
            fields = []
            if yf_data.get("company_name"):
                fields.append(f"Company: {yf_data['company_name']} ({ticker})")
            if yf_data.get("sector"):
                fields.append(f"Sector: {yf_data['sector']} / Industry: {yf_data.get('industry', 'N/A')}")
            if yf_data.get("revenue_ttm"):
                fields.append(f"Revenue (TTM): ${yf_data['revenue_ttm']/1e9:.2f}B")
            if yf_data.get("gross_margins"):
                fields.append(f"Gross Margin: {yf_data['gross_margins']*100:.1f}%")
            if yf_data.get("pe_ratio"):
                fields.append(f"P/E: {yf_data['pe_ratio']:.1f}x")
            context = "\n".join(fields) if fields else ""

        llm_answer = get_llm_answer(question, context, yf_data)
        if llm_answer:
            return llm_answer

    # Step 4: Rule-based fallback
    log.info("Using rule-based fallback")
    return get_rule_based_answer(question, yf_data)


# ============================================================
# A2A EXECUTOR (used by server.py)
# ============================================================

class FinanceExecutor(AgentExecutor):
    """A2A AgentExecutor for the finance agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a finance analysis task."""
        task = context.current_task
        user_input = context.get_user_input()

        # Extract question from A2A message
        question = ""
        if user_input:
            if isinstance(user_input, str):
                question = user_input
            elif hasattr(user_input, 'parts'):
                for part in user_input.parts:
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        question += part.root.text + " "
                    elif hasattr(part, 'text'):
                        question += part.text + " "
            question = question.strip()

        if not question:
            question = "Provide a general financial market overview."

        log.info(f"A2A execute: question length={len(question)}")

        # Send working status
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        # Generate answer
        try:
            answer = answer_finance_question(question)
        except Exception as e:
            log.error(f"Error generating answer: {e}")
            answer = f"I encountered an error analyzing this financial question. Please try rephrasing."

        # Send completed with artifact
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task.id,
                context_id=context.context_id,
                artifact=Artifact(
                    artifact_id=str(uuid.uuid4()),
                    name="financial_analysis",
                    parts=[Part(root=TextPart(text=answer))],
                ),
                append=False,
                last_chunk=True,
            )
        )

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise UnsupportedOperationError("cancel not supported")


# ============================================================
# STANDALONE FASTAPI APP (for direct testing / /a2a/generate endpoint)
# ============================================================

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

if HAS_FASTAPI:
    app = FastAPI(
        title="AutoPilotAI Finance Agent",
        description="A2A finance agent for FinanceBench/AgentBeats evaluation",
        version=AGENT_VERSION
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    AGENT_CARD_JSON = {
        "name": "AutoPilotAI Finance Agent",
        "description": (
            "Autonomous finance agent for FinanceBench evaluation. "
            "Handles quantitative retrieval, GAAP adjustments, beat-or-miss analysis, "
            "trend analysis, financial modeling, and market analysis from SEC filings."
        ),
        "version": AGENT_VERSION,
        "url": "https://agentbeats-finance.chitacloud.dev",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "financebench-qa",
                "name": "FinanceBench Q&A",
                "description": "537-question FinanceBench benchmark: quantitative retrieval, GAAP analysis, beat/miss, trends, financial modeling",
                "tags": ["finance", "sec", "earnings", "benchmark", "10-k"],
                "examples": [
                    "How has Netflix ARPU changed from 2019 to 2024?",
                    "Did TJX beat its Q4 FY2025 pre-tax margin guidance?",
                    "What is AMD's revenue CAGR from 2020 to 2023?"
                ]
            }
        ]
    }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return AGENT_CARD_JSON

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "version": AGENT_VERSION,
            "llm_enabled": HAS_LITELLM and bool(LLM_API_KEY),
            "llm_model": LLM_MODEL if (HAS_LITELLM and LLM_API_KEY) else None,
            "yfinance": HAS_YFINANCE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/a2a/generate")
    async def generate(request: Request):
        """Main evaluation endpoint for FinanceBench/AgentBeats."""
        body = await request.json()
        question = body.get("question", "")
        rubric = body.get("rubric")
        answer = answer_finance_question(question, rubric)
        return {
            "task_id": body.get("task_id", 0),
            "answer": answer,
            "mode": "llm" if (HAS_LITELLM and LLM_API_KEY) else "rule_based",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/")
    async def a2a_jsonrpc(request: Request):
        """A2A JSON-RPC endpoint."""
        body = await request.json()
        method = body.get("method", "")
        params = body.get("params", {})
        rpc_id = body.get("id")

        if method in ("tasks/send", "tasks/sendSubscribe"):
            message = params.get("message", {})
            parts = message.get("parts", [])
            question = ""
            for p in parts:
                if p.get("type") == "text":
                    question = p.get("text", "")
                    break
            if not question:
                question = params.get("text", params.get("query", ""))
            answer = answer_finance_question(question)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "id": str(uuid.uuid4()),
                    "status": "completed",
                    "result": {"parts": [{"type": "text", "text": answer}]}
                }
            }
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "id": rpc_id,
                     "error": {"code": -32601, "message": f"Method not found: {method}"}}
        )


if __name__ == "__main__":
    # Standalone mode for testing
    import sys
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"Q: {q}")
        print(f"A: {answer_finance_question(q)}")
    else:
        if HAS_FASTAPI:
            uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
        else:
            print("FastAPI not available")
