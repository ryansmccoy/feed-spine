"""Tests for feedspine.enricher.job_store - Enrichment job tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from feedspine.enricher.job_store import (
    EnrichmentJob,
    EnrichmentJobRunner,
    JobStatus,
    MemoryEnrichmentJobStore,
)

# =============================================================================
# EnrichmentJob Tests
# =============================================================================


class TestEnrichmentJob:
    """Tests for EnrichmentJob dataclass."""

    def test_create_job(self) -> None:
        """Test creating an enrichment job."""
        job = EnrichmentJob(
            id="test-123",
            enricher="metadata",
        )
        assert job.id == "test-123"
        assert job.enricher == "metadata"
        assert job.status == JobStatus.PENDING
        assert job.layer is None
        assert job.limit == 100
        assert job.records_processed == 0

    def test_job_is_terminal(self) -> None:
        """Test is_terminal property."""
        pending = EnrichmentJob(id="1", enricher="test", status=JobStatus.PENDING)
        running = EnrichmentJob(id="2", enricher="test", status=JobStatus.RUNNING)
        completed = EnrichmentJob(id="3", enricher="test", status=JobStatus.COMPLETED)
        failed = EnrichmentJob(id="4", enricher="test", status=JobStatus.FAILED)
        cancelled = EnrichmentJob(id="5", enricher="test", status=JobStatus.CANCELLED)

        assert not pending.is_terminal
        assert not running.is_terminal
        assert completed.is_terminal
        assert failed.is_terminal
        assert cancelled.is_terminal

    def test_job_duration(self) -> None:
        """Test duration_seconds calculation."""
        now = datetime.now(UTC)
        job = EnrichmentJob(
            id="test",
            enricher="metadata",
            started_at=now - timedelta(seconds=30),
            completed_at=now,
        )
        assert job.duration_seconds is not None
        assert 29 < job.duration_seconds < 31  # Allow for small timing differences

    def test_job_to_dict(self) -> None:
        """Test to_dict serialization."""
        now = datetime.now(UTC)
        job = EnrichmentJob(
            id="test-123",
            enricher="passthrough",
            layer="BRONZE",
            limit=50,
            status=JobStatus.COMPLETED,
            created_at=now,
            records_processed=100,
            records_enriched=90,
            records_skipped=5,
            records_failed=5,
        )
        data = job.to_dict()

        assert data["id"] == "test-123"
        assert data["enricher"] == "passthrough"
        assert data["layer"] == "BRONZE"
        assert data["limit"] == 50
        assert data["status"] == "completed"
        assert data["records_processed"] == 100
        assert data["records_enriched"] == 90


# =============================================================================
# MemoryEnrichmentJobStore Tests
# =============================================================================


class TestMemoryEnrichmentJobStore:
    """Tests for MemoryEnrichmentJobStore."""

    @pytest.fixture
    def job_store(self) -> MemoryEnrichmentJobStore:
        """Create a job store fixture."""
        return MemoryEnrichmentJobStore()

    async def test_initialize_and_close(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test initialize and close lifecycle."""
        await job_store.initialize()
        assert job_store._initialized is True

        await job_store.close()
        assert job_store._initialized is False

    async def test_create_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test creating a job."""
        await job_store.initialize()

        job = await job_store.create_job(
            enricher="metadata",
            layer="BRONZE",
            limit=50,
        )

        assert job.id is not None
        assert job.enricher == "metadata"
        assert job.layer == "BRONZE"
        assert job.limit == 50
        assert job.status == JobStatus.PENDING

    async def test_get_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test retrieving a job by ID."""
        await job_store.initialize()

        created = await job_store.create_job(enricher="passthrough")
        retrieved = await job_store.get_job(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.enricher == "passthrough"

    async def test_get_nonexistent_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test retrieving a non-existent job returns None."""
        await job_store.initialize()

        job = await job_store.get_job("nonexistent")
        assert job is None

    async def test_update_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test updating a job's state."""
        await job_store.initialize()

        job = await job_store.create_job(enricher="metadata")
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.records_processed = 50

        await job_store.update_job(job)

        retrieved = await job_store.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING
        assert retrieved.records_processed == 50

    async def test_list_jobs(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test listing jobs."""
        await job_store.initialize()

        await job_store.create_job(enricher="passthrough")
        await job_store.create_job(enricher="metadata")
        await job_store.create_job(enricher="entity")

        jobs = await job_store.list_jobs()
        assert len(jobs) == 3

    async def test_list_jobs_with_status_filter(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test listing jobs with status filter."""
        await job_store.initialize()

        job1 = await job_store.create_job(enricher="passthrough")
        job2 = await job_store.create_job(enricher="metadata")

        # Mark one as completed
        job1.status = JobStatus.COMPLETED
        await job_store.update_job(job1)

        pending_jobs = await job_store.list_jobs(status=JobStatus.PENDING)
        completed_jobs = await job_store.list_jobs(status=JobStatus.COMPLETED)

        assert len(pending_jobs) == 1
        assert len(completed_jobs) == 1
        assert pending_jobs[0].id == job2.id
        assert completed_jobs[0].id == job1.id

    async def test_max_jobs_limit(self) -> None:
        """Test that max_jobs limit is enforced."""
        job_store = MemoryEnrichmentJobStore(max_jobs=3)
        await job_store.initialize()

        # Create 5 jobs
        for i in range(5):
            job = await job_store.create_job(enricher=f"enricher-{i}")
            # Mark as completed so they can be removed
            job.status = JobStatus.COMPLETED
            await job_store.update_job(job)

        jobs = await job_store.list_jobs()
        # Some jobs should have been removed to stay within max_jobs
        assert len(jobs) <= 3


# =============================================================================
# EnrichmentJobRunner Tests
# =============================================================================


class TestEnrichmentJobRunner:
    """Tests for EnrichmentJobRunner."""

    @pytest.fixture
    def job_store(self) -> MemoryEnrichmentJobStore:
        """Create a job store fixture."""
        return MemoryEnrichmentJobStore()

    async def mock_run_enrichment(self, storage, enricher: str, layer: str | None, limit: int) -> dict:
        """Mock enrichment function."""
        return {
            "processed": 10,
            "enriched": 8,
            "skipped": 1,
            "failed": 1,
        }

    async def mock_run_enrichment_error(self, storage, enricher: str, layer: str | None, limit: int) -> dict:
        """Mock enrichment function that raises an error."""
        raise ValueError("Test error")

    async def test_run_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test running a job successfully."""
        await job_store.initialize()
        job = await job_store.create_job(enricher="metadata")

        runner = EnrichmentJobRunner(job_store, None, self.mock_run_enrichment)
        result = await runner.run_job(job.id)

        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.records_processed == 10
        assert result.records_enriched == 8

    async def test_run_job_with_error(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test running a job that fails."""
        await job_store.initialize()
        job = await job_store.create_job(enricher="metadata")

        runner = EnrichmentJobRunner(job_store, None, self.mock_run_enrichment_error)
        result = await runner.run_job(job.id)

        assert result is not None
        assert result.status == JobStatus.FAILED
        assert result.error_message == "Test error"

    async def test_run_nonexistent_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test running a non-existent job returns None."""
        await job_store.initialize()

        runner = EnrichmentJobRunner(job_store, None, self.mock_run_enrichment)
        result = await runner.run_job("nonexistent")

        assert result is None

    async def test_cancel_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test cancelling a job."""
        await job_store.initialize()
        job = await job_store.create_job(enricher="metadata")

        runner = EnrichmentJobRunner(job_store, None, self.mock_run_enrichment)
        result = await runner.cancel_job(job.id)

        assert result is not None
        assert result.status == JobStatus.CANCELLED

    async def test_cannot_cancel_completed_job(self, job_store: MemoryEnrichmentJobStore) -> None:
        """Test that completed jobs cannot be cancelled (returns as-is)."""
        await job_store.initialize()
        job = await job_store.create_job(enricher="metadata")
        job.status = JobStatus.COMPLETED
        await job_store.update_job(job)

        runner = EnrichmentJobRunner(job_store, None, self.mock_run_enrichment)
        result = await runner.cancel_job(job.id)

        assert result is not None
        assert result.status == JobStatus.COMPLETED  # Unchanged
