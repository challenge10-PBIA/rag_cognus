"""Multi-agent team: Data Engineer, AI Engineer, Security/Test, and Team Lead."""

from __future__ import annotations
import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

# Internal messages use Portuguese per project domain
Message = dict[str, str]


@dataclass(slots=True)
class TaskRequest:
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    description: str
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    context_documents: list[str] | None = None  # JSON snippets, file paths or DB query results
    related_requests: list[str] | None = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass(slots=True)
class TaskResult(BaseModelBase):  # type ignore [name-defined]
    request_id: str
    status: Literal["success", "failure"]
    data_type: Optional[str] = None  # e.g. json, text, report
    content: Union[dict, list, str]
    errors: list[str] | None = field(default_factory=list)

    def to_dict(self):
        result = asdict(self)
        if self.errors is None:
            del result["errors"]
        return result


class AgentType(Enum):
    LEAD      = "lead"           # Team Lead — user-facing, relays and summarizes cross-agent work
    DATA      = "data_engineer"  # Data Engineer ETL pipelines, DB queries, data quality, sync to/from Databricks
    AI        = "ai_engineer"    # LLM orchestration (LangChain), evals, RAG pipeline tuning
    SEC       = "security_test"   # Security checks, unit/integration tests for agents & APIs


class AgentRole(Enum):
    ORCHESTRATE  = "orchestrate" 
    DATA_MODELING  = "data_modeling" 

# Internal message channel types
CHANNEL_TYPE_INTERNAL = "internal_team_channel"
CHANN
