"""
Workspace datamart chat pipeline — simplified SQL agent.

Implementation: ``pipeline.runner.run_chat_pipeline``
"""
from __future__ import annotations

from .pipeline.runner import run_chat_pipeline
from .pipeline.add_scenario_runner import run_add_scenario_turn as _run_add_scenario_pipeline

__all__ = ["run_chat_pipeline", "_run_add_scenario_pipeline"]
