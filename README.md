# AutoPilotAI Finance Agent — AgentBeats Sprint 1

> A2A-compatible agent for the OfficeQA Finance benchmark.
> Built during AgentBeats Phase 2, Sprint 1 (March 2026).

## Overview

This agent answers grounded reasoning questions over US Treasury Bulletins (1939–2025) from the FRASER archive. It retrieves source documents, extracts precise numerical values from financial tables, and performs multi-step computations.

**Team:** AutoPilotAI  
**Author:** Alex Chen — [alexchen.chitacloud.dev](https://alexchen.chitacloud.dev)  
**Track:** Finance (OfficeQA benchmark)  
**Foundation Models:** Claude (Anthropic), GPT-4o (OpenAI) — configurable  
**Compute:** Chita Cloud  
**Live Agent:** [agentbeats-finance.chitacloud.dev](https://agentbeats-finance.chitacloud.dev/.well-known/agent.json)
**AgentBeats:** [fredyk/autopilotai-finance-agent](https://agentbeats.dev/fredyk/autopilotai-finance-agent)
**Docker Image:** `ghcr.io/alexchenai/agentbeats-finance:latest`

## Architecture

```
Question → Year/Month Extraction → FRASER Document Retrieval → LLM Reasoning → <FINAL_ANSWER>
```

1. **Document Retrieval**: Searches the Federal Reserve Bank of St. Louis FRASER archive for the specific Treasury Bulletin matching the question's time period.
2. **Context Augmentation**: Injects relevant document text (up to 40K chars) into the LLM prompt for grounded reasoning.
3. **LLM Inference**: Uses Claude or GPT-4o with web search for precise numerical extraction and multi-step calculations.
4. **Answer Formatting**: All responses use the required `<FINAL_ANSWER>` tag format for evaluator compatibility.

## Capabilities

- **Data Extraction**: Reads values from Treasury Bulletin tables (debt, rates, receipts, expenditures)
- **Multi-Step Computation**: Percentage changes, ratios, year-over-year comparisons
- **Document Grounding**: Answers are tied to specific FRASER archive documents
- **Fallback Chain**: FRASER → Web Search → LLM Knowledge

## A2A Protocol

Implements the [Agent-to-Agent (A2A) protocol](https://github.com/google/A2A) via `a2a-sdk`.

- **Agent Card**: `GET /.well-known/agent.json`
- **Task Send**: `POST /` (JSON-RPC)
- **Streaming**: Supported (SSE)
- **Transport**: JSON-RPC over HTTP

## AgentBeats / Amber

The agent includes an `amber-manifest.json5` for compatibility with the AgentBeats assessment framework. The Docker image is published to `ghcr.io/alexchenai/agentbeats-finance:latest` via GitHub Actions on every push to master.

## Running Locally

```bash
# Set LLM API key
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...

# Install dependencies
pip install -r requirements.txt

# Run
python server.py --port 8080
```

## Docker

```bash
docker build -t agentbeats-finance .
docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... agentbeats-finance
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_MODEL` | `claude-opus-4-5-20251101` | Anthropic model ID |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model ID |
| `ENABLE_WEB_SEARCH` | `true` | Enable web search for document retrieval |

## License

MIT
