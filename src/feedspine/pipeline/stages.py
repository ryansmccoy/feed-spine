"""Pipeline stages - Record processing logic with deduplication.

Provides the process_candidate() function that implements content-hash
based deduplication: create new records, detect duplicates, and handle
content updates.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from spine.events import Event

from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.pipeline.action import ProcessAction
from feedspine.pipeline.result import ProcessResult

if TYPE_CHECKING:
    from feedspine.models.record import RecordCandidate
    from feedspine.pipeline.context import PipelineContext


async def process_candidate(
    ctx: PipelineContext,
    candidate: RecordCandidate,
    source: str,
) -> ProcessResult:
    """Process a single record candidate with content hash-based update detection.

    This function handles three scenarios:
    1. CREATED: New natural_key, store record and record first sighting
    2. DUPLICATE: Same natural_key AND same content_hash, only record sighting
    3. UPDATED: Same natural_key but different content_hash, update record

    Architecture:
        ```
        Processing Flow:
        ┌────────────────┐
        │RecordCandidate │
        │ natural_key    │
        │ content_hash   │
        └───────┬────────┘
                │
                ▼
        ┌───────────────────────────────────────┐
        │ storage.get_by_natural_key(key)       │
        └───────────────────┬───────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
        Not found       Found, same hash   Found, diff hash
            │               │               │
            ▼               ▼               ▼
        ┌───────┐       ┌───────┐       ┌───────┐
        │CREATE │       │DUPLICA│       │UPDATE │
        │new rec│       │record │       │content│
        │+sight │       │sighting│      │+sight │
        └───────┘       └───────┘       └───────┘
        ```

    Args:
        ctx: Pipeline context with storage, notifier, and run log.
        candidate: The record candidate to process.
        source: Source identifier for sighting tracking.

    Returns:
        ProcessResult containing the action taken and the record.

    Raises:
        TypeError: If candidate is None.

    Example:
        >>> import asyncio
        >>> from feedspine.pipeline.context import PipelineContext
        >>> from feedspine.pipeline.stages import process_candidate
        >>> from feedspine import MemoryStorage, RecordCandidate
        >>> from datetime import datetime, UTC
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     await storage.initialize()
        ...     ctx = PipelineContext(storage=storage)
        ...     c = RecordCandidate(
        ...         natural_key="acc-001",
        ...         title="Filing",
        ...         published_at=datetime.now(UTC),
        ...         metadata={"source": "test"},
        ...     )
        ...     result = await process_candidate(ctx, c, source="test")
        ...     return result.is_new
        >>> asyncio.run(example())
        True

    Tags:
        - deduplication, record_processing, pipeline, content_hash
    """
    if candidate is None:
        raise TypeError("candidate cannot be None")

    # Check if record already exists (per-feed dedup via natural_key)
    existing = await ctx.storage.get_by_natural_key(candidate.natural_key)

    if existing is not None:
        return await _handle_existing(ctx, candidate, existing, source)

    # Cross-feed dedup: check content hash across all feeds
    if ctx.dedup_index is not None:
        match = ctx.dedup_index.check(candidate.content_hash)
        if match.is_duplicate:
            # Same content already stored from another feed — record sighting only
            existing_record = await ctx.storage.get(match.existing_record_id)
            if existing_record is not None:
                sighting = Sighting(
                    id=str(uuid.uuid4()),
                    natural_key=candidate.natural_key,
                    source=source,
                    record_id=existing_record.id,
                    is_new=False,
                )
                await ctx.storage.record_sighting(sighting)
                return ProcessResult(
                    action=ProcessAction.DUPLICATE,
                    record=existing_record,
                    previous_content_hash=None,
                )

    return await _handle_new(ctx, candidate, source)


async def _handle_existing(
    ctx: PipelineContext,
    candidate: RecordCandidate,
    existing: Record,
    source: str,
) -> ProcessResult:
    """Handle a candidate that matches an existing record.

    Compares content hashes to determine if this is a true duplicate
    or a content update.

    Args:
        ctx: Pipeline context.
        candidate: The incoming record candidate.
        existing: The existing record with the same natural key.
        source: Source identifier for sighting tracking.

    Returns:
        ProcessResult with DUPLICATE or UPDATED action.
    """
    candidate_hash = candidate.content_hash
    existing_hash = existing.content_hash

    if existing_hash == candidate_hash:
        # Same content - record sighting only (true duplicate)
        sighting = Sighting(
            id=str(uuid.uuid4()),
            natural_key=candidate.natural_key,
            source=source,
            record_id=existing.id,
            is_new=False,
        )
        await ctx.storage.record_sighting(sighting)
        return ProcessResult(
            action=ProcessAction.DUPLICATE,
            record=existing,
            previous_content_hash=None,
        )

    # Content changed - update the record
    previous_hash = existing.content_hash
    updated_record = existing.update_content(
        new_content=candidate.content,
        new_hash=candidate.content_hash,
    )
    await ctx.storage.store(updated_record)

    # Record sighting for the update
    sighting = Sighting(
        id=str(uuid.uuid4()),
        natural_key=candidate.natural_key,
        source=source,
        record_id=updated_record.id,
        is_new=False,
    )
    await ctx.storage.record_sighting(sighting)
    return ProcessResult(
        action=ProcessAction.UPDATED,
        record=updated_record,
        previous_content_hash=previous_hash,
    )


async def _handle_new(
    ctx: PipelineContext,
    candidate: RecordCandidate,
    source: str,
) -> ProcessResult:
    """Handle a candidate with no existing record (new record).

    Creates the record, stores it, records the first sighting,
    and optionally sends a notification.

    Args:
        ctx: Pipeline context.
        candidate: The new record candidate.
        source: Source identifier for sighting tracking.

    Returns:
        ProcessResult with CREATED action.
    """
    # Create new record from candidate with generated UUID
    record_id = str(uuid.uuid4())
    record = Record.from_candidate(candidate, record_id)

    # Store the record
    await ctx.storage.store(record)

    # Record first sighting
    sighting = Sighting(
        id=str(uuid.uuid4()),
        natural_key=record.natural_key,
        source=source,
        record_id=record.id,
        is_new=True,
    )
    await ctx.storage.record_sighting(sighting)

    # Register in cross-feed dedup index
    if ctx.dedup_index is not None:
        ctx.dedup_index.register(record.content_hash, record.id)

    # Notify if configured
    if ctx.event_bus is not None:
        title = record.content.get("title", record.natural_key)
        event = Event(
            event_type="feed.record.created",
            source="feed-spine",
            payload={"title": title, "record_id": record.id, "natural_key": record.natural_key, "source": source},
        )
        await ctx.event_bus.publish(event)

    return ProcessResult(
        action=ProcessAction.CREATED,
        record=record,
        previous_content_hash=None,
    )
