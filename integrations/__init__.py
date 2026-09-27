"""
Integrations package for CapEcon.

This package provides adapters for popular agent frameworks (LangGraph, CrewAI, AutoGen).
These adapters allow CapEcon to ingest traces and generate GDRs from different agent runtimes.

Critical principle: These adapters do NOT replace existing OTel/Langfuse adapters.
They are ADDITIONAL adapters for specific frameworks.
"""

from integrations.langgraph import LangGraphAdapter
from integrations.crewai import CrewAIAdapter
from integrations.autogen import AutoGenAdapter
from integrations.otel import OTelAdapter

__all__ = [
    "LangGraphAdapter",
    "CrewAIAdapter",
    "AutoGenAdapter",
    "OTelAdapter",
]
