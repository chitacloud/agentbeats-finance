#!/usr/bin/env python3
"""
ChitaCloud Finance Agent - AgentBeats Sprint 1 Entry
SEC 10-K Analysis: Risk Classification, Business Summary, Consistency Check

A2A Protocol compliant agent using official a2a-sdk.
Competition: AgentBeats Phase 2, Sprint 1 - Finance Track
"""

import argparse
import logging
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent import FinanceExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("finance_server")


def main():
    parser = argparse.ArgumentParser(description="ChitaCloud Finance Agent - SEC 10-K Analysis")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--card-url", type=str, default=None)
    args = parser.parse_args()

    skills = [
        AgentSkill(
            id="risk_classification",
            name="SEC 10-K Risk Factor Classification",
            description="Classifies risk factors from SEC 10-K Section 1A into 12 predefined categories: Market, Operational, Financial, Regulatory, Cybersecurity, Supply Chain, Reputational, Strategic, Macroeconomic, Environmental, Human Capital, Technology",
            tags=["finance", "sec", "10-k", "risk"],
        ),
        AgentSkill(
            id="business_summary",
            name="SEC 10-K Business Summary Extraction",
            description="Extracts industry type, products/services, and geographic markets from SEC 10-K Section 1",
            tags=["finance", "sec", "10-k", "summary"],
        ),
        AgentSkill(
            id="consistency_check",
            name="SEC 10-K Cross-Section Consistency Check",
            description="Verifies whether risks identified in Section 1A are discussed in Section 7 MD&A",
            tags=["finance", "sec", "10-k", "consistency"],
        ),
    ]

    card = AgentCard(
        name="chitacloud_finance_agent",
        description="Finance agent for AgentBeats Sprint 1. Analyzes SEC 10-K filings: risk factor classification (12 categories), business summary extraction, and cross-section consistency verification between Section 1A and MD&A.",
        url=args.card_url or f"http://{args.host}:{args.port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    handler = DefaultRequestHandler(
        agent_executor=FinanceExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=card,
        http_handler=handler,
    )

    log.info(f"Starting ChitaCloud Finance Agent on {args.host}:{args.port}")
    log.info(f"Agent card URL: {args.card_url or f'http://{args.host}:{args.port}/'}")
    uvicorn.run(server.build(), host=args.host, port=args.port, timeout_keep_alive=300)


if __name__ == "__main__":
    main()
