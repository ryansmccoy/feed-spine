"""Pipeline package - Core feed processing orchestrator.

This package provides the feed processing pipeline components:
- ProcessAction: Enum for record processing outcomes
- ProcessResult: Structured result from processing a candidate
- PipelineStats: Aggregated run statistics
- PipelineContext: Dependency container for pipeline stages
- Pipeline: Core orchestrator with deduplication (facade)

Submodules:
- context: PipelineContext dependency container
- stages: process_candidate() deduplication logic
- runner: run_feed() feed orchestration
- action: ProcessAction enum
- result: ProcessResult dataclass
- stats: PipelineStats dataclass
- core: Pipeline facade class

Re-exports all components for backward compatibility with:
    from feedspine.pipeline import Pipeline, ProcessAction, ...
"""

from feedspine.pipeline.action import ProcessAction
from feedspine.pipeline.context import PipelineContext
from feedspine.pipeline.core import Pipeline
from feedspine.pipeline.dedup import DedupIndex, DedupMatch, DedupStats
from feedspine.pipeline.result import ProcessResult
from feedspine.pipeline.runner import run_feed
from feedspine.pipeline.stages import process_candidate
from feedspine.pipeline.stats import PipelineStats

__all__ = [
    "Pipeline",
    "PipelineContext",
    "PipelineStats",
    "ProcessAction",
    "ProcessResult",
    "process_candidate",
    "run_feed",
]
