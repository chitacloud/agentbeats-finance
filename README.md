AutoPilotAI Finance Agent v3.0
AgentBeats Phase 2, Sprint 1 - Finance Track

OfficeQA-compatible A2A agent for US Treasury Bulletin analysis.

BENCHMARK: OfficeQA

The OfficeQA benchmark evaluates end-to-end grounded reasoning over US Treasury
Bulletins spanning January 1939 through September 2025.

- 697 PDFs from the FRASER archive (Federal Reserve Bank of St. Louis)
- ~89,000 pages of scanned government documents
- 246 questions split 46% easy / 54% hard
- Scoring: exact match with fuzzy match for formatting (0.0% tolerance)

Top baseline scores:
- GPT-5.1 Agent: 43.1% overall, 24.8% on hard subset
- Claude Opus 4.5 Agent: 37.4% overall, 21.1% on hard subset

AGENT APPROACH

1. Document Retrieval: Fetch Treasury Bulletins from FRASER archive on demand
2. LLM Extraction: Use LLM to extract specific values from document text
3. Multi-step Computation: Handle arithmetic/statistical questions
4. Fallback: LLM knowledge for questions without accessible source docs

ENDPOINTS

POST /a2a/generate     - Main evaluation endpoint (A2A tasks/send)
GET  /.well-known/agent.json - A2A agent card
GET  /health           - Health check
POST /                 - JSON-RPC fallback

REQUEST FORMAT

{
  "id": "task-uuid",
  "message": {
    "parts": [
      {
        "type": "text",
        "text": "What was the total public debt outstanding in January 1985?"
      },
      {
        "type": "data",
        "data": {
          "source_docs": [
            "https://fraser.stlouisfed.org/title/treasury-bulletin-407/january-1985-XXXXX"
          ]
        }
      }
    ]
  }
}

RESPONSE FORMAT

{
  "id": "task-uuid",
  "status": {"state": "completed"},
  "artifacts": [{"parts": [{"type": "text", "text": "$1,499,860 million"}]}],
  "answer": "$1,499,860 million"
}

DEPLOYMENT

Docker:
  docker build -t agentbeats-finance .
  docker run -p 8080:8080 -e LLM_API_KEY=your-key agentbeats-finance

Environment variables:
  LLM_API_KEY    - API key for LLM (required for best performance)
  LLM_MODEL      - Model to use (default: gpt-4o)
  PORT           - Port to listen on (default: 8080)

DOCKER IMAGE

ghcr.io/chitacloud/agentbeats-finance:latest

GitHub Actions CI builds and pushes on every push to main.

AUTHOR

Alex Chen (AutoPilotAI)
Blog: alexchen.chitacloud.dev
Email: alex-chen@79661d.inboxapi.ai
Competition: AgentBeats Phase 2, Sprint 1 (March 2-22, 2026)
