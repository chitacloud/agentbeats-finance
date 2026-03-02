# ChitaCloud Finance Agent - AgentBeats Sprint 1

SEC 10-K filing analysis agent built on the A2A protocol for [AgentBeats Phase 2](https://rdi.berkeley.edu/agentx-agentbeats.html) (UC Berkeley RDI + Google DeepMind).

**Competition:** AgentBeats Phase 2, Sprint 1 - Finance Track
**Team:** ChitaCloud (chitacloud.dev)
**Docker:** `ghcr.io/chitacloud/agentbeats-finance:v1.0`

## What This Agent Does

Analyzes SEC 10-K filings with three capabilities:

1. **Risk Factor Classification** (40% weight) - Classifies Section 1A risk factors into 12 predefined categories (Market, Operational, Financial, Regulatory/Compliance, Cybersecurity, Supply Chain, Reputational, Strategic, Macroeconomic, Environmental, Human Capital, Technology)

2. **Business Summary Extraction** (30% weight) - Extracts industry type, products/services, and geographic markets from Section 1

3. **Cross-Section Consistency Check** (30% weight) - Verifies whether risks from Section 1A are discussed in Section 7 (MD&A)

## Quick Start

```bash
docker pull ghcr.io/chitacloud/agentbeats-finance:v1.0

docker run -p 8080:8080 \
  -e LLM_MODEL=anthropic/claude-sonnet-4-20250514 \
  -e LLM_API_KEY=your-api-key \
  ghcr.io/chitacloud/agentbeats-finance:v1.0
```

Test the agent card:
```bash
curl http://localhost:8080/.well-known/agent-card.json
```

## A2A Protocol

This agent implements the [A2A protocol](https://a2a-protocol.org/) using the official `a2a-sdk`:
- Agent card: `GET /.well-known/agent-card.json`
- Task execution: `POST /` (JSON-RPC 2.0, method `tasks/send`)
- Accepts `--host`, `--port`, `--card-url` arguments

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `anthropic/claude-sonnet-4-20250514` | LiteLLM model identifier |
| `LLM_API_KEY` | - | API key for the LLM provider |
| `LLM_API_BASE` | - | Custom API base URL (for self-hosted LLMs) |

## Building

```bash
docker build --platform linux/amd64 -t agentbeats-finance:v1.0 .
docker run -p 8080:8080 -e LLM_API_KEY=sk-... agentbeats-finance:v1.0
```

## Architecture

- `server.py` - A2A server entry point (argparse + Starlette)
- `agent.py` - SEC 10-K analysis logic (task detection, LLM prompting, JSON extraction)
- Uses [LiteLLM](https://github.com/BerriAI/litellm) for model flexibility
- Stateless per-task analysis, no external dependencies beyond LLM API
