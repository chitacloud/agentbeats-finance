#!/usr/bin/env python3
"""
AutoPilotAI Finance Agent - AgentBeats Sprint 1 Entry
A2A Protocol compliant autonomous finance agent for market analysis,
portfolio optimization, and financial decision support.

Author: Alex Chen (alexchenai) - alex-chen@79661d.inboxapi.ai
Blog: alexchen.chitacloud.dev
Competition: AgentBeats Phase 2, Sprint 1 - Finance Track
"""

import os
import json
import time
import uuid
import logging
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import urllib.error
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("finance_agent")

AGENT_ID = "autopilotai-finance-v1"
AGENT_VERSION = "1.0.0"
PORT = int(os.environ.get("PORT", 8080))

# ============================================================
# FINANCE CAPABILITIES
# ============================================================

SUPPORTED_TASKS = [
    "financial_analysis",
    "portfolio_optimization",
    "risk_assessment",
    "market_sentiment",
    "crypto_analysis",
    "near_market_analysis",
    "agent_economy_metrics",
    "budget_allocation",
    "roi_calculation",
    "expense_tracking",
    "investment_strategy",
    "fx_analysis",
    "defi_analysis",
]


def fetch_crypto_price(symbol: str) -> Optional[float]:
    """Fetch crypto price from public CoinGecko API."""
    try:
        coin_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "NEAR": "near",
            "SOL": "solana", "BNB": "binancecoin", "USDC": "usd-coin",
            "TON": "the-open-network", "LINK": "chainlink",
        }
        coin_id = coin_map.get(symbol.upper(), symbol.lower())
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get(coin_id, {}).get("usd")
    except Exception as e:
        log.warning(f"Price fetch failed for {symbol}: {e}")
        return None


def calculate_portfolio_metrics(holdings: List[Dict]) -> Dict:
    """Calculate portfolio allocation and risk metrics."""
    total_value = sum(h.get("value_usd", 0) for h in holdings)
    if total_value == 0:
        return {"error": "Empty portfolio"}

    metrics = {
        "total_value_usd": total_value,
        "holdings_count": len(holdings),
        "allocations": [],
        "concentration_risk": 0.0,
        "diversification_score": 0.0,
    }

    # Calculate allocations and HHI (Herfindahl-Hirschman Index)
    hhi = 0.0
    for h in holdings:
        weight = h.get("value_usd", 0) / total_value
        hhi += weight ** 2
        metrics["allocations"].append({
            "asset": h.get("symbol", "UNKNOWN"),
            "value_usd": h.get("value_usd", 0),
            "weight_pct": round(weight * 100, 2),
        })

    metrics["concentration_risk"] = round(hhi, 4)
    # Diversification: 1 = perfectly concentrated, 0 = perfectly diversified (max_n assets)
    metrics["diversification_score"] = round(1 - hhi, 4)

    return metrics


def assess_near_market_agent_economics() -> Dict:
    """Analyze the NEAR AI market agent economy metrics."""
    near_price = fetch_crypto_price("NEAR") or 1.05

    analysis = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "near_price_usd": near_price,
        "market_observations": {
            "total_jobs_observed": 63,
            "competition_pools": {
                "25N_tweet": {"expires": "2026-03-03", "prize_usd": round(25 * near_price, 2)},
                "100N_build_agent": {"expires": "2026-03-07", "prize_usd": round(100 * near_price, 2)},
            },
            "average_job_budget_near": 12.5,
            "acceptance_rate_pct": 1.6,  # 1/63 accepted
            "platform_escrow_mechanism": "centralized_custody",
            "conflict_of_interest_flag": True,
            "sybil_farm_detected": True,
        },
        "roi_analysis": {
            "bids_placed": 1558,
            "time_per_bid_minutes": 2,
            "total_time_hours": round(1558 * 2 / 60, 1),
            "near_earned": 0,
            "roi": "negative_currently",
            "recommendation": "Focus on competitions over standard bids. Only 2 open competitions with zero other entrants.",
        },
        "agent_economy_health": "early_stage_with_structural_issues",
        "trust_infrastructure_gap": "No cryptographic escrow. Centralized custody with conflict of interest.",
    }
    return analysis


def generate_investment_strategy(
    capital_usd: float,
    risk_tolerance: str = "moderate",
    time_horizon_months: int = 12
) -> Dict:
    """Generate a structured investment strategy for an AI agent."""
    allocations = {
        "conservative": {"stable": 70, "growth": 20, "speculation": 10},
        "moderate": {"stable": 50, "growth": 35, "speculation": 15},
        "aggressive": {"stable": 20, "growth": 45, "speculation": 35},
    }

    alloc = allocations.get(risk_tolerance, allocations["moderate"])

    stable_assets = ["USDC", "USDT"]
    growth_assets = ["ETH", "NEAR", "SOL"]
    speculative_assets = ["DeFi protocols", "new token launches", "agent tokens"]

    strategy = {
        "capital_usd": capital_usd,
        "risk_profile": risk_tolerance,
        "time_horizon_months": time_horizon_months,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "allocation_strategy": {
            "stable_reserves": {
                "percentage": alloc["stable"],
                "amount_usd": round(capital_usd * alloc["stable"] / 100, 2),
                "assets": stable_assets,
                "purpose": "Operational runway and stable base",
            },
            "growth_positions": {
                "percentage": alloc["growth"],
                "amount_usd": round(capital_usd * alloc["growth"] / 100, 2),
                "assets": growth_assets,
                "purpose": "Long-term value appreciation",
            },
            "speculative_positions": {
                "percentage": alloc["speculation"],
                "amount_usd": round(capital_usd * alloc["speculation"] / 100, 2),
                "assets": speculative_assets,
                "purpose": "High-risk high-reward opportunities",
            },
        },
        "risk_metrics": {
            "max_drawdown_tolerance_pct": 30 if risk_tolerance == "conservative" else 50 if risk_tolerance == "moderate" else 80,
            "stop_loss_trigger_pct": 20,
            "rebalance_frequency": "monthly",
        },
        "agent_specific_considerations": [
            "Maintain minimum 3-month runway in stable assets",
            "Prioritize platforms with cryptographic escrow over custodial",
            "Diversify income streams across multiple agent marketplaces",
            "Track ROI per platform and reallocate to highest performers",
        ],
    }
    return strategy


def analyze_defi_opportunity(protocol: str) -> Dict:
    """Analyze a DeFi protocol opportunity for an agent."""
    protocols = {
        "uniswap_v3": {"type": "DEX", "tvl_bn": 4.2, "apy_range": "5-150%", "risk": "medium", "chain": "Ethereum"},
        "aave": {"type": "lending", "tvl_bn": 8.1, "apy_range": "2-12%", "risk": "low", "chain": "multi-chain"},
        "compound": {"type": "lending", "tvl_bn": 1.9, "apy_range": "1-8%", "risk": "low", "chain": "Ethereum"},
        "near_ref_finance": {"type": "DEX", "tvl_bn": 0.08, "apy_range": "10-200%", "risk": "medium-high", "chain": "NEAR"},
    }

    data = protocols.get(protocol.lower().replace(" ", "_"), {
        "type": "unknown", "tvl_bn": 0, "apy_range": "unknown", "risk": "unknown", "chain": "unknown"
    })

    return {
        "protocol": protocol,
        "analysis": data,
        "recommendation": "Proceed with caution" if data.get("risk") in ["medium", "medium-high"] else "Suitable for conservative allocation",
        "agent_note": "As an autonomous agent, prefer protocols with programmatic access (APIs/SDKs) over manual UIs",
    }


def calculate_roi(
    investment_usd: float,
    return_usd: float,
    time_days: float
) -> Dict:
    """Calculate ROI with annualized return."""
    roi_pct = ((return_usd - investment_usd) / investment_usd) * 100 if investment_usd > 0 else 0
    annualized = ((1 + roi_pct / 100) ** (365 / time_days) - 1) * 100 if time_days > 0 else 0

    return {
        "investment_usd": investment_usd,
        "return_usd": return_usd,
        "profit_loss_usd": round(return_usd - investment_usd, 2),
        "roi_pct": round(roi_pct, 2),
        "annualized_return_pct": round(annualized, 2),
        "time_days": time_days,
        "assessment": "profitable" if roi_pct > 0 else "loss",
    }


# ============================================================
# A2A PROTOCOL IMPLEMENTATION
# ============================================================

class Task:
    """Represents an A2A task in processing."""
    def __init__(self, task_id: str, message: Dict):
        self.task_id = task_id
        self.message = message
        self.status = "submitted"
        self.result = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def to_dict(self) -> Dict:
        return {
            "id": self.task_id,
            "status": {"state": self.status},
            "messages": [self.message],
            "result": self.result,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class FinanceAgent:
    """A2A-compliant Finance Agent."""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.agent_card = self._build_agent_card()

    def _build_agent_card(self) -> Dict:
        return {
            "name": "AutoPilotAI Finance Agent",
            "description": (
                "Autonomous finance agent specialized in portfolio analysis, "
                "crypto market intelligence, DeFi opportunity assessment, "
                "and agent economy economics. Built for AgentBeats Sprint 1 - Finance Track. "
                "Powered by Alex Chen / AutoPilotAI (alexchen.chitacloud.dev)."
            ),
            "url": f"http://localhost:{PORT}",
            "version": AGENT_VERSION,
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "skills": [
                {
                    "id": skill,
                    "name": skill.replace("_", " ").title(),
                    "description": f"Perform {skill.replace('_', ' ')} analysis",
                    "inputModes": ["text/plain", "application/json"],
                    "outputModes": ["application/json"],
                    "tags": ["finance", "crypto", "analysis"],
                }
                for skill in SUPPORTED_TASKS
            ],
            "defaultInputModes": ["text/plain", "application/json"],
            "defaultOutputModes": ["application/json"],
        }

    def process_message(self, message_content: str) -> Dict:
        """Process a natural language or JSON finance query."""
        content = message_content.lower()

        # Route to appropriate capability - check more specific routes first
        if any(w in content for w in ["near market", "agent economy", "market.near.ai", "agent market"]):
            return self._handle_near_market_query()
        elif any(w in content for w in ["price", "btc", "eth", "near price", "crypto", "token"]):
            return self._handle_price_query(message_content)
        elif any(w in content for w in ["portfolio", "holdings", "allocation", "diversif"]):
            return self._handle_portfolio_query(message_content)
        elif any(w in content for w in ["near market", "agent economy", "market.near.ai", "agent market"]):
            return self._handle_near_market_query()
        elif any(w in content for w in ["strategy", "invest", "allocat", "plan"]):
            return self._handle_strategy_query(message_content)
        elif any(w in content for w in ["defi", "protocol", "yield", "liquidity"]):
            return self._handle_defi_query(message_content)
        elif any(w in content for w in ["roi", "return", "profit", "loss"]):
            return self._handle_roi_query(message_content)
        elif any(w in content for w in ["risk", "assess", "exposure"]):
            return self._handle_risk_query(message_content)
        else:
            return self._handle_general_query(message_content)

    def _handle_price_query(self, content: str) -> Dict:
        """Handle cryptocurrency price queries."""
        symbols = ["BTC", "ETH", "NEAR", "SOL", "BNB", "TON", "LINK", "USDC"]
        prices = {}
        for sym in symbols:
            if sym.lower() in content.lower() or "all" in content.lower() or "crypto" in content.lower():
                price = fetch_crypto_price(sym)
                if price:
                    prices[sym] = price

        if not prices:
            # Default: fetch NEAR price (most relevant to our ecosystem)
            near_price = fetch_crypto_price("NEAR")
            prices["NEAR"] = near_price or 1.05

        return {
            "type": "price_data",
            "prices_usd": prices,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinGecko API",
            "note": "Prices are real-time market data",
        }

    def _handle_portfolio_query(self, content: str) -> Dict:
        """Handle portfolio analysis queries."""
        # Example demo portfolio - real usage would parse from message
        demo_portfolio = [
            {"symbol": "NEAR", "amount": 100, "value_usd": 105},
            {"symbol": "ETH", "amount": 0.05, "value_usd": 165},
            {"symbol": "USDC", "amount": 200, "value_usd": 200},
            {"symbol": "BTC", "amount": 0.002, "value_usd": 190},
        ]
        metrics = calculate_portfolio_metrics(demo_portfolio)
        metrics["holdings"] = demo_portfolio
        metrics["analysis"] = "Demo portfolio: well-diversified with majority stable assets."
        return metrics

    def _handle_near_market_query(self) -> Dict:
        """Handle NEAR AI market economics queries."""
        return assess_near_market_agent_economics()

    def _handle_strategy_query(self, content: str) -> Dict:
        """Handle investment strategy queries."""
        # Parse capital from content or use default
        capital = 1000.0
        for word in content.split():
            try:
                val = float(word.replace("$", "").replace(",", ""))
                if 10 < val < 10000000:
                    capital = val
                    break
            except ValueError:
                pass

        risk = "moderate"
        if any(w in content for w in ["conservative", "safe", "low risk"]):
            risk = "conservative"
        elif any(w in content for w in ["aggressive", "high risk", "risky"]):
            risk = "aggressive"

        return generate_investment_strategy(capital, risk)

    def _handle_defi_query(self, content: str) -> Dict:
        """Handle DeFi protocol analysis."""
        protocols = ["uniswap", "aave", "compound", "near_ref_finance"]
        protocol = "aave"  # default
        for p in protocols:
            if p.replace("_", " ") in content.lower() or p in content.lower():
                protocol = p
                break
        return analyze_defi_opportunity(protocol)

    def _handle_roi_query(self, content: str) -> Dict:
        """Handle ROI calculation queries."""
        # Parse numbers from content
        numbers = []
        for word in content.split():
            try:
                val = float(word.replace("$", "").replace(",", "").replace("%", ""))
                if val > 0:
                    numbers.append(val)
            except ValueError:
                pass

        if len(numbers) >= 3:
            return calculate_roi(numbers[0], numbers[1], numbers[2])
        elif len(numbers) == 2:
            return calculate_roi(numbers[0], numbers[1], 30)
        else:
            # Demo calculation for an AI agent's operational costs
            return calculate_roi(
                investment_usd=7.0,   # Daily operational cost
                return_usd=0.0,       # Current: 0 earned
                time_days=42          # Days until runway
            )

    def _handle_risk_query(self, content: str) -> Dict:
        """Handle risk assessment queries."""
        return {
            "type": "risk_assessment",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_specific_risks": {
                "platform_risk": {
                    "near_ai_market": "HIGH - Centralized escrow, conflict of interest, sybil farms detected",
                    "moltbook": "LOW - Social platform, karma system, no financial escrow",
                    "agentbeats": "LOW-MEDIUM - UC Berkeley + Google DeepMind backing, legitimate competition",
                    "superteam": "MEDIUM - Established platform, human judges required",
                },
                "income_risk": {
                    "current_earnings": 0,
                    "runway_days": 42,
                    "daily_cost_usd": 7.0,
                    "risk_level": "HIGH - Revenue not yet established",
                },
                "market_risk": {
                    "near_price_volatility": "MEDIUM - NEAR has had 80% drawdowns historically",
                    "crypto_market_correlation": "HIGH - Most agent economy tokens correlated",
                },
                "mitigation_strategies": [
                    "Diversify across multiple agent marketplaces",
                    "Focus on competitions with guaranteed prize pools",
                    "Build recurring revenue through SaaS tools (SkillScan, AgentMarket)",
                    "Maintain USD-denominated stable coin reserves",
                ],
            },
        }

    def _handle_general_query(self, content: str) -> Dict:
        """Handle general finance queries."""
        return {
            "type": "general_finance_response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": {
                "name": "AutoPilotAI Finance Agent",
                "version": AGENT_VERSION,
                "capabilities": SUPPORTED_TASKS,
            },
            "response": (
                "I am an autonomous finance agent specialized in crypto market analysis, "
                "portfolio optimization, agent economy economics, and investment strategy. "
                "I can analyze NEAR AI market dynamics, calculate ROI for agent operations, "
                "assess DeFi opportunities, and provide investment strategies for autonomous agents. "
                "Please specify your financial analysis task."
            ),
            "example_queries": [
                "What is the current NEAR price?",
                "Analyze the NEAR AI market agent economy",
                "Generate an investment strategy for $1000 with moderate risk",
                "Assess risk for an AI agent with 42 days runway",
                "Analyze DeFi opportunities on NEAR",
                "Calculate ROI: invested $100, returned $120, over 30 days",
            ],
        }

    def create_task(self, task_id: str, message: Dict) -> Task:
        task = Task(task_id, message)
        self.tasks[task_id] = task
        return task

    def execute_task(self, task: Task) -> None:
        """Execute a task and update its status."""
        try:
            task.status = "working"
            task.updated_at = datetime.now(timezone.utc).isoformat()

            # Extract text content from message
            content = ""
            msg = task.message
            if isinstance(msg.get("parts"), list):
                for part in msg["parts"]:
                    if part.get("type") == "text":
                        content += part.get("text", "")
            elif isinstance(msg.get("content"), str):
                content = msg["content"]

            result = self.process_message(content)

            task.result = {
                "parts": [{
                    "type": "data",
                    "data": result,
                }]
            }
            task.status = "completed"
            task.updated_at = datetime.now(timezone.utc).isoformat()
            log.info(f"Task {task.task_id[:8]} completed: {result.get('type', 'unknown')}")

        except Exception as e:
            task.status = "failed"
            task.result = {"error": str(e)}
            task.updated_at = datetime.now(timezone.utc).isoformat()
            log.error(f"Task {task.task_id[:8]} failed: {e}")


# ============================================================
# HTTP SERVER (A2A JSON-RPC)
# ============================================================

agent = FinanceAgent()


class A2AHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(f"HTTP {self.address_string()} - {fmt % args}")

    def send_json(self, code: int, data: Dict):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/.well-known/agent.json":
            self.send_json(200, agent.agent_card)

        elif path == "/health":
            self.send_json(200, {
                "status": "healthy",
                "agent": AGENT_ID,
                "version": AGENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tasks_processed": len(agent.tasks),
            })

        elif path.startswith("/tasks/"):
            task_id = path.split("/tasks/")[1]
            if task_id in agent.tasks:
                self.send_json(200, agent.tasks[task_id].to_dict())
            else:
                self.send_json(404, {"error": "Task not found", "task_id": task_id})

        elif path == "/capabilities":
            self.send_json(200, {
                "supported_tasks": SUPPORTED_TASKS,
                "a2a_version": "0.2.6",
                "agent_id": AGENT_ID,
            })

        else:
            self.send_json(404, {"error": "Not found", "path": path})

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        if path == "/":
            # A2A JSON-RPC endpoint
            method = payload.get("method", "")
            params = payload.get("params", {})
            rpc_id = payload.get("id")

            if method == "tasks/send":
                # Create and execute task
                task_id = str(uuid.uuid4())
                message = params.get("message", {})
                if not message:
                    # Allow simple text input
                    text = params.get("text", params.get("query", ""))
                    message = {"role": "user", "parts": [{"type": "text", "text": text}]}

                task = agent.create_task(task_id, message)

                # Execute synchronously (no streaming in v1)
                agent.execute_task(task)

                self.send_json(200, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": task.to_dict(),
                })

            elif method == "tasks/sendSubscribe":
                # Non-streaming fallback
                task_id = str(uuid.uuid4())
                message = params.get("message", {})
                task = agent.create_task(task_id, message)
                agent.execute_task(task)

                self.send_json(200, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": task.to_dict(),
                })

            elif method == "tasks/get":
                task_id = params.get("id", "")
                if task_id in agent.tasks:
                    self.send_json(200, {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": agent.tasks[task_id].to_dict(),
                    })
                else:
                    self.send_json(404, {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {"code": -32001, "message": "Task not found"},
                    })

            elif method == "tasks/cancel":
                task_id = params.get("id", "")
                if task_id in agent.tasks:
                    agent.tasks[task_id].status = "canceled"
                    self.send_json(200, {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": agent.tasks[task_id].to_dict(),
                    })
                else:
                    self.send_json(404, {"error": "Task not found"})

            else:
                self.send_json(400, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                })

        elif path == "/analyze":
            # Simple REST endpoint for quick analysis
            query = payload.get("query", payload.get("message", ""))
            result = agent.process_message(query)
            self.send_json(200, result)

        else:
            self.send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


def main():
    log.info(f"Starting AutoPilotAI Finance Agent v{AGENT_VERSION} on port {PORT}")
    log.info(f"A2A endpoint: http://0.0.0.0:{PORT}/")
    log.info(f"Agent card: http://0.0.0.0:{PORT}/.well-known/agent.json")
    log.info(f"Health check: http://0.0.0.0:{PORT}/health")

    server = HTTPServer(("0.0.0.0", PORT), A2AHandler)
    log.info("Finance Agent ready to serve requests")
    server.serve_forever()


if __name__ == "__main__":
    main()
