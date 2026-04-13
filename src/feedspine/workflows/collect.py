"""FeedCollectionRuntime — spine-core Runtime for feed.collect workflow.

Thin bridge between the execution engine and the domain service layer.
Contains no business logic — delegates to:

- ``FeedCollectionService``: runs the collection (domain execution)
- ``CollectionOutcomeRecorder``: writes operational facts
- ``CollectionEventPublisher``: emits completion event (LAST)

Follows the *Collection Completion Ordering Contract*:

1. Domain execution  (service.run_collection)
2. Operational recording  (recorder.record)
3. Event emission  (publisher.publish_completed)
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from feedspine._vendor.execution import (
    ExecutionErrorCategory,
    ExecutionHandle,
    ExecutionState,
    ExecutionStatus,
)
from feedspine._vendor.logging import get_logger

# ExecutionRequest is a discriminated union from spine.runtime.requests;
# we only need it for type annotations here.
ExecutionRequest = Any

from feedspine.services.collection import CollectionOutcome, FeedCollectionService
from feedspine.services.publishing import CollectionEventPublisher
from feedspine.services.recording import CollectionOutcomeRecorder

logger = get_logger(__name__)


class FeedCollectionRuntime:
    """Bridge: execution engine → domain service layer.

    Implements ``spine.runtime.runtime.Runtime`` protocol.

    Args:
        collection_service: Domain service that runs feed collection.
        recorder: Records operational side effects after collection.
        publisher: Emits completion events via EventStore.
    """

    def __init__(
        self,
        collection_service: FeedCollectionService,
        recorder: CollectionOutcomeRecorder,
        publisher: CollectionEventPublisher,
    ) -> None:
        self._service = collection_service
        self._recorder = recorder
        self._publisher = publisher
        self._tasks: dict[str, asyncio.Task[CollectionOutcome]] = {}

    @property
    def name(self) -> str:
        """Runtime name used for scoring and selection."""
        return "feed-collection"

    def score(self, request: ExecutionRequest) -> int:
        """Score this runtime for the given request.

        Returns 100 for ``feed.collect`` requests, 0 otherwise.
        """
        request_name = getattr(request, "name", None)
        if request_name == "feed.collect":
            return 100
        return 0

    async def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Submit a feed collection for execution.

        Extracts ``feed_name`` from the request parameters, then
        runs the collection pipeline asynchronously.

        Args:
            request: Execution request (typically ``AgentRequest``).

        Returns:
            Handle for tracking execution status.
        """
        feed_name = self._extract_feed_name(request)

        handle = ExecutionHandle.create(
            runtime_name=self.name,
            external_ref=str(uuid4()),
            request_name=request.name,
        )

        async def _run() -> CollectionOutcome:
            # 1. Domain execution
            outcome = await self._service.run_collection(feed_name)
            # 2. Operational recording
            self._recorder.record(outcome)
            # 3. Event emission (last — makes outcome externally actionable)
            self._publisher.publish_completed(outcome)
            return outcome

        task = asyncio.create_task(_run())
        self._tasks[handle.execution_id] = task
        logger.info(
            "Submitted feed.collect for %r (execution_id=%s)",
            feed_name,
            handle.execution_id,
        )
        return handle

    async def status(self, handle: ExecutionHandle) -> ExecutionStatus:
        """Check execution status for a running collection."""
        task = self._tasks.get(handle.execution_id)
        if task is None:
            return ExecutionStatus(
                handle=handle,
                state=ExecutionState.FAILED,
                error="Unknown execution",
                error_category=ExecutionErrorCategory.UNKNOWN,
            )
        if not task.done():
            return ExecutionStatus(
                handle=handle,
                state=ExecutionState.RUNNING,
            )
        exc = task.exception() if not task.cancelled() else None
        if task.cancelled():
            return ExecutionStatus(
                handle=handle,
                state=ExecutionState.CANCELLED,
            )
        if exc is not None:
            return ExecutionStatus(
                handle=handle,
                state=ExecutionState.FAILED,
                error=str(exc),
                error_category=ExecutionErrorCategory.HANDLER_ERROR,
            )
        # Success — extract result as output dict
        outcome = task.result()
        return ExecutionStatus(
            handle=handle,
            state=ExecutionState.COMPLETED,
            started_at=outcome.started_at,
            completed_at=outcome.completed_at,
            output=self._outcome_to_dict(outcome),
        )

    async def cancel(self, handle: ExecutionHandle) -> bool:
        """Cancel a running collection."""
        task = self._tasks.get(handle.execution_id)
        if task is not None and not task.done():
            task.cancel()
            logger.info(
                "Cancelled feed.collect (execution_id=%s)",
                handle.execution_id,
            )
            return True
        return False

    @staticmethod
    def _extract_feed_name(request: ExecutionRequest) -> str:
        """Extract feed_name from request params."""
        # AgentRequest has .params; all request types have .envelope.params
        params: dict[str, Any] = getattr(request, "params", {}) or {}
        if "feed_name" in params:
            return params["feed_name"]
        envelope_params = getattr(getattr(request, "envelope", None), "params", {})
        if "feed_name" in envelope_params:
            return envelope_params["feed_name"]
        raise ValueError("Request missing required 'feed_name' parameter")

    @staticmethod
    def _outcome_to_dict(outcome: CollectionOutcome) -> dict[str, Any]:
        """Convert outcome to a serialisable dict for ExecutionStatus.output."""
        return {
            "feed_name": outcome.feed_name,
            "records_stored": outcome.records_stored,
            "processed": outcome.stats.processed,
            "new": outcome.stats.new,
            "duplicates": outcome.stats.duplicates,
            "updated": outcome.stats.updated,
            "errors": outcome.stats.errors,
            "duration_ms": outcome.stats.duration_ms,
        }
