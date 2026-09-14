"""Pipeline step trace for datamart chat (API + UI)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PipelineStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


# Ordered steps shown in the UI (simplified agent pathway).
PIPELINE_STEP_DEFS: list[tuple[str, str]] = [
    ("schema_grounding", "Load context (catalog + DataHub + warehouse)"),
    ("generate_sql", "Generate SQL"),
    ("execute_query", "Run query on warehouse"),
]


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    status: PipelineStepStatus = PipelineStepStatus.PENDING
    detail: Optional[str] = None
    duration_ms: Optional[int] = None


class RecoveryEvent(BaseModel):
    """One recovery action during the SQL attempt loop (shown in UI)."""

    model_config = ConfigDict(extra="forbid")

    attempt: int
    phase: str
    issue: str
    action: str
    detail: str
    user_message: str


class PipelineTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[PipelineStep] = Field(default_factory=list)
    repair_attempts_used: int = 0
    repair_attempts_max: int = 1
    recovery_events: list[RecoveryEvent] = Field(default_factory=list)


@dataclass
class _StepRuntime:
    status: PipelineStepStatus = PipelineStepStatus.PENDING
    detail: Optional[str] = None
    started_at: Optional[float] = None
    duration_ms: Optional[int] = None


@dataclass
class PipelineTracer:
    """Records agent pathway for one chat turn."""

    repair_attempts_max: int = 1
    _steps: dict[str, _StepRuntime] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    repair_attempts_used: int = 0
    _recovery_events: list[RecoveryEvent] = field(default_factory=list)

    @classmethod
    def begin(cls, *, repair_attempts_max: int = 1) -> PipelineTracer:
        tracer = cls(repair_attempts_max=repair_attempts_max)
        for step_id, label in PIPELINE_STEP_DEFS:
            tracer._order.append(step_id)
            tracer._steps[step_id] = _StepRuntime()
        tracer._notify()
        return tracer

    def _notify(self) -> None:
        from .pipeline_events import emit_pipeline_trace

        emit_pipeline_trace(self)

    def start(self, step_id: str, detail: Optional[str] = None) -> None:
        rt = self._steps.get(step_id)
        if rt is None:
            return
        rt.status = PipelineStepStatus.RUNNING
        rt.detail = detail
        rt.started_at = time.perf_counter()
        self._notify()

    def complete(
        self,
        step_id: str,
        status: PipelineStepStatus,
        detail: Optional[str] = None,
    ) -> None:
        rt = self._steps.get(step_id)
        if rt is None:
            return
        if rt.started_at is not None:
            rt.duration_ms = int((time.perf_counter() - rt.started_at) * 1000)
        rt.status = status
        if detail is not None:
            rt.detail = detail
        self._notify()

    def skip_remaining(self, after_step_id: str, *, reason: str) -> None:
        found = False
        for step_id in self._order:
            if step_id == after_step_id:
                found = True
                continue
            if not found:
                continue
            rt = self._steps[step_id]
            if rt.status in (PipelineStepStatus.PENDING, PipelineStepStatus.RUNNING):
                rt.status = PipelineStepStatus.SKIPPED
                rt.detail = reason
        self._notify()

    def note_recovery(
        self,
        *,
        attempt: int,
        phase: str,
        issue: str,
        action: str,
        detail: str,
        user_message: str,
    ) -> None:
        self.repair_attempts_used += 1
        self._recovery_events.append(
            RecoveryEvent(
                attempt=attempt,
                phase=phase,
                issue=issue,
                action=action,
                detail=detail[:300],
                user_message=user_message[:400],
            )
        )
        self._notify()

    def note_repair(self, detail: str, *, success: bool) -> None:
        self.repair_attempts_used += 1
        self.complete(
            "sql_repair",
            PipelineStepStatus.COMPLETED if success else PipelineStepStatus.WARNING,
            detail,
        )

    def build(self) -> PipelineTrace:
        labels = dict(PIPELINE_STEP_DEFS)
        steps: list[PipelineStep] = []
        for step_id in self._order:
            rt = self._steps[step_id]
            steps.append(
                PipelineStep(
                    id=step_id,
                    label=labels.get(step_id, step_id),
                    status=rt.status,
                    detail=rt.detail,
                    duration_ms=rt.duration_ms,
                )
            )
        return PipelineTrace(
            steps=steps,
            repair_attempts_used=self.repair_attempts_used,
            repair_attempts_max=self.repair_attempts_max,
            recovery_events=list(self._recovery_events),
        )
