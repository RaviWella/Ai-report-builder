"""Per-turn chat context: validation state, pipeline trace, repair budget."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import config as dm_config
from ..models import DatamartResponse, PipelineTurnMeta
from ..pipeline_retry import RepairBudget
from ..pipeline_trace import PipelineTracer
from ..validation.pipeline_validation import PipelineValidationState, finish_validated_response
from ..schema_broker import SchemaGrounding


@dataclass
class ChatRunContext:
    question: str
    pval: PipelineValidationState
    trace: PipelineTracer
    repair_budget: RepairBudget
    turn_meta: PipelineTurnMeta

    @classmethod
    def begin(cls, question: str) -> ChatRunContext:
        max_repairs = dm_config.DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN
        return cls(
            question=question,
            pval=PipelineValidationState(question=question),
            trace=PipelineTracer.begin(repair_attempts_max=max_repairs),
            repair_budget=RepairBudget(max_attempts=max_repairs),
            turn_meta=PipelineTurnMeta(),
        )

    def record_schema_link(
        self,
        *,
        domain: str,
        tables: list[str],
        max_tables: int = 12,
    ) -> None:
        self.turn_meta = self.turn_meta.model_copy(
            update={
                "domain": domain,
                "tables_linked": tables[:max_tables],
            }
        )

    def record_sql_resolve(
        self,
        *,
        tier: str,
        sql_source: str | None,
    ) -> None:
        tier_up = (tier or "C").upper()[:1]
        if tier_up not in ("A", "B", "C"):
            tier_up = "C"
        self.turn_meta = self.turn_meta.model_copy(
            update={
                "sql_tier": tier_up,  # type: ignore[arg-type]
                "sql_source": sql_source,
            }
        )

    def finish(
        self,
        resp: DatamartResponse,
        *,
        sql: Optional[str] = None,
        grounding: Optional[SchemaGrounding] = None,
        binding_passed: bool = True,
        row_count: int = 0,
        run_critic: bool = True,
        awaiting_clarification: bool = False,
    ) -> DatamartResponse:
        out = finish_validated_response(
            self.pval,
            resp,
            sql=sql if sql is not None else resp.sql,
            grounding=grounding,
            binding_passed=binding_passed,
            row_count=row_count or resp.row_count or 0,
            run_critic=run_critic,
            awaiting_clarification=awaiting_clarification,
        )
        return out.model_copy(
            update={
                "pipeline_trace": self.trace.build(),
                "pipeline_meta": self.turn_meta,
            }
        )

    def finish_clarification(
        self,
        resp: DatamartResponse,
        *,
        grounding: Optional[SchemaGrounding] = None,
        sql: Optional[str] = None,
        row_count: int = 0,
    ) -> DatamartResponse:
        """Failed turn: plain summary text (optional clarify UI when enabled)."""
        return self.finish(
            resp,
            sql=sql,
            grounding=grounding,
            binding_passed=False,
            row_count=row_count,
            run_critic=False,
            awaiting_clarification=dm_config.DATAMART_CHAT_CLARIFICATION_UI,
        )
