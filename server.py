#!/usr/bin/env python3
"""
AutoPilotAI Finance Agent Server - AgentBeats Sprint 1
OfficeQA benchmark: US Treasury Bulletin grounded reasoning.

Serves the A2A-compatible FinanceExecutor on the configured host/port.
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
    parser = argparse.ArgumentParser(description="AutoPilotAI Finance Agent - OfficeQA US Treasury Bulletin QA")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--card-url", type=str, default=None)
    args = parser.parse_args()

    skill = AgentSkill(
        id="treasury_bulletin_qa",
        name="US Treasury Bulletin Question Answering",
        description=(
            "Answers grounded reasoning questions over US Treasury Bulletins "
            "(1939-2025) from the FRASER archive. Capable of data extraction from "
            "tables/figures, multi-step financial computations, statistical analysis, "
            "and complex financial metric calculations."
        ),
        tags=["finance", "treasury", "document-qa", "grounded-reasoning", "officeqa"],
        examples=[
            "What was the total public debt outstanding in January 1985?",
            "Calculate the percent change in receipts between 1939 and 1940.",
            "What were the total expenditures in fiscal year 1952?",
        ],
    )

    card = AgentCard(
        name="AutoPilotAI Finance Agent",
        description=(
            "AgentBeats Sprint 1 Finance Track entry. OfficeQA-compatible agent "
            "for US Treasury Bulletin grounded reasoning. Retrieves documents from "
            "FRASER archive, extracts precise numerical values, and performs "
            "multi-step financial computations over 697 PDFs spanning 1939-2025."
        ),
        url=args.card_url or "https://agentbeats-finance.chitacloud.dev/",
        version="4.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    handler = DefaultRequestHandler(
        agent_executor=FinanceExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=card,
        http_handler=handler,
    )

    log.info(f"Starting AutoPilotAI Finance Agent v4.0 on {args.host}:{args.port}")
    log.info(f"Benchmark: OfficeQA - US Treasury Bulletins (1939-2025)")
    card_url = args.card_url or "https://agentbeats-finance.chitacloud.dev/"
    log.info(f"Card URL: {card_url}")
    uvicorn.run(server.build(), host=args.host, port=args.port, timeout_keep_alive=300)


if __name__ == "__main__":
    main()
