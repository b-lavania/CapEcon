"""Drop prompt/response bodies from ingested telemetry. Metadata only."""

from __future__ import annotations

from typing import Any

# Keys commonly used for free-text LLM payloads across OTel GenAI, Langfuse, LangSmith.
CONTENT_KEYS = frozenset(
    {
        "prompt",
        "prompts",
        "response",
        "responses",
        "completion",
        "completions",
        "content",
        "input",
        "output",
        "messages",
        "message",
        "chat_messages",
        "generation",
        "text",
        "body",
        "raw_input",
        "raw_output",
        "llm_input",
        "llm_output",
        "input_messages",
        "output_messages",
        "gen_ai.prompt",
        "gen_ai.completion",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "langchain.prompt",
        "ai.prompt",
        "ai.completion",
    }
)

CONTENT_KEY_FRAGMENTS = ("prompt", "completion", "message", "content")

ALLOWED_SPAN_COLUMNS = frozenset(
    {
        "span_id",
        "agent_run_id",
        "run_id",
        "session_id",
        "parent_span_id",
        "loop_iteration",
        "tokens_in",
        "tokens_out",
        "tokens_used",
        "success",
        "trace_id",
        "data_source",
        "span_type",
        "name",
        "status",
        "started_at",
        "completed_at",
        "cost_usd",
        "capability_id",
        "model_id",
        "scrubbed",
    }
)


def _is_content_key(key: str) -> bool:
    k = key.lower().replace("-", "_")
    # Token *counts* are metadata (RouteLLM / FrugalGPT), not prompt bodies.
    if k.endswith("_tokens") or k in {"tokens_in", "tokens_out", "tokens_used", "cached_tokens"}:
        return False
    if k in CONTENT_KEYS:
        return True
    # Nested OTel attribute style: gen_ai.prompt.0.content
    parts = k.replace(".", "_").split("_")
    if any(p in {"prompt", "completion", "message", "messages", "content"} for p in parts) and any(
        frag in k for frag in ("prompt", "completion", "message", "content")
    ):
        if k in {"capability_id", "success", "status", "span_type", "parent_span_id"}:
            return False
        if "prompt" in k or "completion" in k or k.endswith("_content") or "messages" in k:
            return True
    return False


def scrub_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `row` with free-text LLM fields removed."""
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if _is_content_key(str(key)):
            continue
        if isinstance(value, dict):
            cleaned[key] = scrub_payload(value)
        elif isinstance(value, list):
            cleaned[key] = [
                scrub_payload(v) if isinstance(v, dict) else v
                for v in value
                if not (isinstance(v, str) and key.lower() in CONTENT_KEYS)
            ]
        else:
            cleaned[key] = value
    cleaned["scrubbed"] = True
    return cleaned


def span_has_content(row: dict[str, Any]) -> bool:
    """True if a span dict still carries a known content key."""
    for key in row:
        if _is_content_key(str(key)):
            return True
        val = row[key]
        if isinstance(val, dict) and span_has_content(val):
            return True
    return False
