"""Enrichment Job Store for background enrichment processing.

Provides job tracking for asynchronous enrichment operations. Jobs can be
queued, tracked, and their results retrieved.

Example:
    >>> store = MemoryEnrichmentJobStore()
    >>> await store.initialize()
    >>> job = await store.create_job(enricher="metadata", layer="BRONZE", limit=100)
    >>> print(job.id, job.status)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from feedspine.types import JobId

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


class JobStatus(StrEnum):
    """Enrichment job status."""

    PENDING = "pending"  # Job queued, not started
    RUNNING = "running"  # Job in progress
    COMPLETED = "completed"  # Job finished successfully
    FAILED = "failed"  # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled


@dataclass
class EnrichmentJob:
    """Represents an enrichment job.

    Attributes:
        id: Unique job identifier.
        enricher: Name of the enricher to use.
        layer: Target layer to enrich (optional).
        limit: Maximum records to process.
        status: Current job status.
        created_at: When the job was created.
        started_at: When processing started.
        completed_at: When processing finished.
        records_processed: Number of records processed.
        records_enriched: Number of records successfully enriched.
        records_skipped: Number of records skipped.
        records_failed: Number of records that failed enrichment.
        error_message: Error message if job failed.
        metadata: Additional job metadata.
    """

    id: JobId
    enricher: str
    layer: str | None = None
    limit: int = 100
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_processed: int = 0
    records_enriched: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "enricher": self.enricher,
            "layer": self.layer,
            "limit": self.limit,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "records_processed": self.records_processed,
            "records_enriched": self.records_enriched,
            "records_skipped": self.records_skipped,
            "records_failed": self.records_failed,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


class EnrichmentJobStore:
    """Abstract base for enrichment job storage."""

    async def initialize(self) -> None:
        """Initialize the job store."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the job store."""
        raise NotImplementedError

    async def create_job(
        self,
        enricher: str,
        *,
        layer: str | None = None,
        limit: int = 100,
        metadata: dict[str, Any] | None = None,
    ) -> EnrichmentJob:
        """Create a new enrichment job."""
        raise NotImplementedError

    async def get_job(self, job_id: JobId) -> EnrichmentJob | None:
        """Get a job by ID."""
        raise NotImplementedError

    async def update_job(self, job: EnrichmentJob) -> None:
        """Update a job's state."""
        raise NotImplementedError

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[EnrichmentJob]:
        """List jobs with optional filtering."""
        raise NotImplementedError


class MemoryEnrichmentJobStore(EnrichmentJobStore):
    """In-memory implementation of enrichment job store.

    Suitable for development, testing, and single-process deployments.
    Jobs are lost when the process exits.

    Example:
        >>> store = MemoryEnrichmentJobStore()
        >>> await store.initialize()
        >>> job = await store.create_job("metadata", layer="BRONZE")
        >>> print(job.status)
        JobStatus.PENDING
    """

    def __init__(self, max_jobs: int = 1000) -> None:
        """Initialize the in-memory job store.

        Args:
            max_jobs: Maximum number of jobs to retain (oldest removed first).
        """
        self._jobs: dict[JobId, EnrichmentJob] = {}
        self._max_jobs = max_jobs
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the job store."""
        self._initialized = True

    async def close(self) -> None:
        """Close the job store."""
        self._jobs.clear()
        self._initialized = False

    async def create_job(
        self,
        enricher: str,
        *,
        layer: str | None = None,
        limit: int = 100,
        metadata: dict[str, Any] | None = None,
    ) -> EnrichmentJob:
        """Create a new enrichment job.

        Args:
            enricher: Name of the enricher to use.
            layer: Target layer to enrich (optional).
            limit: Maximum records to process.
            metadata: Additional job metadata.

        Returns:
            The created EnrichmentJob.
        """
        job_id = JobId(str(uuid.uuid4())[:8])
        job = EnrichmentJob(
            id=job_id,
            enricher=enricher,
            layer=layer,
            limit=limit,
            metadata=metadata or {},
        )

        # Enforce max jobs limit
        if len(self._jobs) >= self._max_jobs:
            # Remove oldest completed/failed jobs first
            terminal_jobs = sorted(
                [j for j in self._jobs.values() if j.is_terminal],
                key=lambda j: j.created_at,
            )
            for old_job in terminal_jobs[: len(self._jobs) - self._max_jobs + 1]:
                del self._jobs[old_job.id]

        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: JobId) -> EnrichmentJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    async def update_job(self, job: EnrichmentJob) -> None:
        """Update a job's state."""
        if job.id in self._jobs:
            self._jobs[job.id] = job

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[EnrichmentJob]:
        """List jobs with optional filtering.

        Args:
            status: Filter by job status.
            limit: Maximum jobs to return.

        Returns:
            List of EnrichmentJob objects, newest first.
        """
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]


class EnrichmentJobRunner:
    """Runs enrichment jobs in the background.

    Coordinates job execution with the job store. Jobs are executed
    asynchronously and their status is updated in the store.

    Example:
        >>> store = MemoryEnrichmentJobStore()
        >>> runner = EnrichmentJobRunner(store, storage, run_func)
        >>> job = await store.create_job("metadata")
        >>> await runner.run_job(job.id)
    """

    def __init__(
        self,
        job_store: EnrichmentJobStore,
        storage: Any,
        run_enrichment: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        """Initialize the job runner.

        Args:
            job_store: The job store for tracking job state.
            storage: Storage backend for accessing records.
            run_enrichment: Async function that performs the actual enrichment.
                           Should accept (storage, enricher, layer, limit) and return
                           a dict with {processed, enriched, skipped, failed} counts.
        """
        self._job_store = job_store
        self._storage = storage
        self._run_enrichment = run_enrichment
        self._running_jobs: set[str] = set()

    async def run_job(self, job_id: str) -> EnrichmentJob | None:
        """Run a job by ID.

        Args:
            job_id: The job to run.

        Returns:
            The updated job, or None if not found.
        """
        job = await self._job_store.get_job(job_id)
        if job is None:
            return None

        if job.is_terminal:
            return job  # Already finished

        if job_id in self._running_jobs:
            return job  # Already running

        self._running_jobs.add(job_id)

        try:
            # Mark as running
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
            await self._job_store.update_job(job)

            # Execute the enrichment
            result = await self._run_enrichment(
                self._storage,
                job.enricher,
                job.layer,
                job.limit,
            )

            # Update with results
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.records_processed = result.get("processed", 0)
            job.records_enriched = result.get("enriched", 0)
            job.records_skipped = result.get("skipped", 0)
            job.records_failed = result.get("failed", 0)
            await self._job_store.update_job(job)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(UTC)
            job.error_message = str(e)
            await self._job_store.update_job(job)
        finally:
            self._running_jobs.discard(job_id)

        return job

    def run_job_background(self, job_id: str) -> asyncio.Task:
        """Run a job in the background.

        Args:
            job_id: The job to run.

        Returns:
            An asyncio.Task that can be awaited optionally.
        """
        return asyncio.create_task(self.run_job(job_id))

    async def cancel_job(self, job_id: str) -> EnrichmentJob | None:
        """Cancel a pending or running job.

        Note: Running jobs may not stop immediately.

        Args:
            job_id: The job to cancel.

        Returns:
            The updated job, or None if not found.
        """
        job = await self._job_store.get_job(job_id)
        if job is None:
            return None

        if job.is_terminal:
            return job  # Already finished

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(UTC)
        await self._job_store.update_job(job)

        return job
