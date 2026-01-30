"""Pydantic models for FeedSpine."""

from feedspine.models.base import FeedSpineModel, Layer, Metadata
from feedspine.models.content import (
    ContentSchema,
    TypedRecord,
    clear_content_registry,
    get_content_schema,
    register_content_schema,
)
from feedspine.models.converter import (
    ConverterRegistry,
    RecordConverter,
    converter_registry,
)
from feedspine.models.feed_run import FeedRun, FeedRunStatus
from feedspine.models.query import Query, QuerySpec
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting
from feedspine.models.task import Task, TaskResult, TaskStatus

__all__ = [
    # Base
    "FeedSpineModel",
    "Layer",
    "Metadata",
    # Content typing
    "ContentSchema",
    "TypedRecord",
    "register_content_schema",
    "get_content_schema",
    "clear_content_registry",
    # Converter registry
    "ConverterRegistry",
    "RecordConverter",
    "converter_registry",
    # Query builder
    "Query",
    "QuerySpec",
    # Records
    "Record",
    "RecordCandidate",
    "Sighting",
    # Feed runs (operational tracking)
    "FeedRun",
    "FeedRunStatus",
    # Tasks
    "Task",
    "TaskResult",
    "TaskStatus",
]
