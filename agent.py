"""
SEC 10-K Analysis Agent - Core Logic
Handles risk classification, business summary, and consistency check tasks
from the Alpha-Cortex-AI green agent evaluator.
"""

import os
import json
import re
import logging

import litellm

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InvalidRequestError,
    TaskState,
    UnsupportedOperationError,
)
from a2a.utils import new_agent_text_message, new_task, new_text_artifact
from a2a.utils.errors import ServerError

log = logging.getLogger("finance_agent")

TERMINAL_STATES = {
    TaskState.completed,
    TaskState.canceled,
    TaskState.failed,
    TaskState.rejected,
}

RISK_CATEGORIES = [
    "Market Risk",
    "Operational Risk",
    "Financial Risk",
    "Regulatory/Compliance Risk",
    "Cybersecurity Risk",
    "Supply Chain Risk",
    "Reputational Risk",
    "Strategic Risk",
    "Macroeconomic Risk",
    "Environmental Risk",
    "Human Capital Risk",
    "Technology Risk",
]

SYSTEM_PROMPT = """You are an expert SEC financial analyst. You analyze 10-K filings with precision and return structured JSON.

You handle three task types:

1. RISK CLASSIFICATION: Given Section 1A text, identify ALL applicable risk categories.
   Valid categories: Market Risk, Operational Risk, Financial Risk, Regulatory/Compliance Risk, Cybersecurity Risk, Supply Chain Risk, Reputational Risk, Strategic Risk, Macroeconomic Risk, Environmental Risk, Human Capital Risk, Technology Risk.
   Output format: {"risk_classification": ["Category1", "Category2", ...]}

2. BUSINESS SUMMARY: Given Section 1 text, extract structured business information.
   Output format: {"industry": "specific industry", "products_services": "key offerings", "geographic_markets": "markets served"}

3. CONSISTENCY CHECK: Given Section 1A + Section 7 text, verify risk coverage in MD&A.
   Output format: {"consistency_check": {"risk_discussed_in_mda": true/false, "evidence": "specific citations"}}

RULES:
- Output ONLY valid JSON. No markdown, no explanation, no preamble.
- For risk classification, be thorough. Most 10-K filings have 4-8 applicable categories.
- For business summaries, be specific and factual. Extract from the text, do not infer.
- For consistency checks, cite specific phrases from the MD&A as evidence.
- If you cannot determine the task type, default to risk classification."""


def detect_task_type(text: str) -> str:
    """Detect which evaluation task the green agent is requesting."""
    lower = text.lower()

    # Consistency check: must have BOTH Section 1A and Section 7/MD&A references
    has_1a = "section 1a" in lower or "risk factors" in lower
    has_7 = (
        "section 7" in lower
        or "md&a" in lower
        or "management's discussion" in lower
        or "management discussion" in lower
    )
    if has_1a and has_7:
        return "consistency_check"

    # Explicit consistency keywords
    if any(
        kw in lower
        for kw in ["consistency", "cross-section", "verify", "discussed in"]
    ):
        if has_7:
            return "consistency_check"

    # Business summary keywords
    if any(
        kw in lower
        for kw in [
            "business summary",
            "section 1 ",
            "section 1\n",
            "industry type",
            "products_services",
            "products/services",
            "geographic_markets",
            "geographic markets",
        ]
    ):
        return "business_summary"

    # Risk classification keywords
    if any(
        kw in lower
        for kw in [
            "risk_classification",
            "risk classification",
            "risk categories",
            "risk factors",
            "section 1a",
            "classify",
            "categorize",
        ]
    ):
        return "risk_classification"

    # Fallback heuristic
    if lower.count("risk") > 3:
        return "risk_classification"

    return "risk_classification"


def build_prompt(task_type: str, text: str) -> str:
    """Build task-specific prompt for the LLM."""
    if task_type == "risk_classification":
        categories_str = "\n".join(f"  - {c}" for c in RISK_CATEGORIES)
        return f"""Analyze the following SEC 10-K text and classify which risk categories apply.

Select ALL categories that are discussed or implied in the text:
{categories_str}

TEXT:
{text}

Return ONLY valid JSON: {{"risk_classification": ["Category1", "Category2", ...]}}"""

    elif task_type == "business_summary":
        return f"""Analyze the following SEC 10-K business description and extract structured information.

TEXT:
{text}

Return ONLY valid JSON:
{{"industry": "<specific industry type>", "products_services": "<concise description of key products and services>", "geographic_markets": "<geographic markets served>"}}"""

    elif task_type == "consistency_check":
        return f"""Analyze the following SEC 10-K sections. Determine whether the risk factors from Section 1A are adequately discussed in the Management's Discussion and Analysis (Section 7/MD&A).

{text}

Return ONLY valid JSON:
{{"consistency_check": {{"risk_discussed_in_mda": true or false, "evidence": "<specific quotes or references from the MD&A that address or fail to address the identified risks>"}}}}"""

    return f"""Analyze this SEC financial text and provide structured analysis in JSON format.

{text}"""


def extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling wrappers."""
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text

    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]

    return text


def fallback_response(task_type: str, error: str) -> str:
    """Return valid JSON fallback if LLM fails."""
    if task_type == "risk_classification":
        return json.dumps(
            {"risk_classification": ["Financial Risk", "Market Risk", "Operational Risk"]}
        )
    elif task_type == "business_summary":
        return json.dumps(
            {
                "industry": "Unable to determine",
                "products_services": "Unable to analyze",
                "geographic_markets": "Unable to determine",
            }
        )
    elif task_type == "consistency_check":
        return json.dumps(
            {
                "consistency_check": {
                    "risk_discussed_in_mda": False,
                    "evidence": f"Analysis unavailable: {error}",
                }
            }
        )
    return json.dumps({"error": error})


def normalize_categories(categories: list) -> list:
    """Ensure risk categories match the exact official names."""
    valid = []
    for cat in categories:
        # Exact match
        matched = next(
            (c for c in RISK_CATEGORIES if c.lower() == cat.lower()),
            None,
        )
        if matched:
            if matched not in valid:
                valid.append(matched)
            continue
        # Partial match
        matched = next(
            (
                c
                for c in RISK_CATEGORIES
                if cat.lower() in c.lower() or c.lower() in cat.lower()
            ),
            None,
        )
        if matched and matched not in valid:
            valid.append(matched)
    return valid


class FinanceAgent:
    """Core SEC 10-K analysis agent using LLM."""

    def __init__(self):
        self.model = os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-20250514")
        self.api_base = os.environ.get("LLM_API_BASE")
        self.api_key = os.environ.get("LLM_API_KEY")
        log.info(f"FinanceAgent initialized: model={self.model}")

    async def analyze(self, text: str) -> str:
        """Analyze SEC 10-K text and return structured JSON."""
        task_type = detect_task_type(text)
        log.info(f"Task type detected: {task_type}")

        prompt = build_prompt(task_type, text)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2000,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key

        try:
            response = await litellm.acompletion(**kwargs)
            result = response.choices[0].message.content
            result = extract_json(result)

            parsed = json.loads(result)

            # Post-process risk categories to match exact names
            if task_type == "risk_classification" and "risk_classification" in parsed:
                normalized = normalize_categories(parsed["risk_classification"])
                if normalized:
                    parsed["risk_classification"] = normalized
                    result = json.dumps(parsed)

            log.info(f"Analysis complete ({task_type}): {result[:200]}...")
            return result

        except json.JSONDecodeError:
            log.warning(f"Invalid JSON from LLM, returning raw")
            return result
        except Exception as e:
            log.error(f"LLM call failed: {e}", exc_info=True)
            return fallback_response(task_type, str(e))


class FinanceExecutor(AgentExecutor):
    """A2A executor routing messages to the FinanceAgent."""

    def __init__(self):
        self.agents: dict[str, FinanceAgent] = {}

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        msg = context.message
        if not msg:
            raise ServerError(error=InvalidRequestError(message="Missing message"))

        task = context.current_task
        if task and task.status.state in TERMINAL_STATES:
            raise ServerError(
                error=InvalidRequestError(
                    message=f"Task {task.id} already in terminal state"
                )
            )

        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)

        context_id = task.context_id
        updater = TaskUpdater(event_queue, task.id, context_id)
        await updater.start_work()

        try:
            agent = self.agents.get(context_id)
            if not agent:
                agent = FinanceAgent()
                self.agents[context_id] = agent

            # Extract text from message parts
            text_parts = []
            for part in msg.parts:
                p = getattr(part, "root", part)
                if hasattr(p, "text"):
                    text_parts.append(p.text)

            user_text = "\n".join(text_parts)

            if not user_text.strip():
                await updater.failed(
                    new_agent_text_message(
                        "No text content in message",
                        context_id=context_id,
                        task_id=task.id,
                    )
                )
                return

            log.info(f"Processing message ({len(user_text)} chars)")
            result = await agent.analyze(user_text)

            await updater.add_artifact(
                new_text_artifact(result, name="sec_10k_analysis")
            )
            await updater.complete()

        except Exception as e:
            log.error(f"Execution error: {e}", exc_info=True)
            await updater.failed(
                new_agent_text_message(
                    f"Analysis failed: {str(e)}",
                    context_id=context_id,
                    task_id=task.id,
                )
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
