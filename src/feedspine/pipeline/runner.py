"""Pipeline runner - Feed orchestration and event logging.

Provides the run_feed() function that orchestrates fetching candidates
from a feed adapter, processing them through deduplication stages,
and emitting run lifecycle events.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from spine.core.logging import LogScope, get_logger

from feedspine.core.exceptions import FeedSpineError
from feedspine.models.run_event import RunEvent
from feedspine.pipeline.action import ProcessAction
from feedspine.pipeline.stages import process_candidate
from feedspine.pipeline.stats import PipelineStats

logger = get_logger(__name__)

if TYPE_CHECKING:
    from feedspine.pipeline.context import PipelineContext
    from feedspine.protocols.feed import FeedAdapter


async def run_feed(ctx: PipelineContext, feed: FeedAdapter) -> PipelineStats:
    """Run the pipeline for a feed adapter.

    Fetches all candidates from the feed and processes them through
    deduplication stages. If a run_log is configured on the context,
    emits RUN_STARTED, RECORD_*, and RUN_COMPLETED events.

    Architecture:
        ```
        run_feed(ctx, feed)
              │
              ├─► emit RUN_STARTED
              │
              ├─► for candidate in feed.fetch():
              │       result = process_candidate(ctx, candidate, feed.name)
              │       stats.update(result)
              │       emit RECORD_* event
              │
              ├─► emit RUN_COMPLETED
              │
              └─► return PipelineStats
        ```

    Args:
        ctx: Pipeline context with storage, notifier, and run log.
        feed: The feed adapter to process.

    Returns:
        Statistics about the pipeline run.

    Raises:
        Exception: Re-raises any feed-level exception after logging RUN_ERROR.

    Example:
        >>> import asyncio
        >>> from feedspine.pipeline.context import PipelineContext
        >>> from feedspine.pipeline.runner import run_feed
        >>> from feedspine import MemoryStorage
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     await storage.initialize()
        ...     ctx = PipelineContext(storage=storage)
        ...     # Would need a feed adapter here
        ...     return True
        >>> asyncio.run(example())
        True

    Tags:
        - pipeline, orchestration, feed_processing, run_management
    """
    run_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    stats = PipelineStats(feed_name=feed.name)

    async with LogScope(run_id=run_id, feed_name=feed.name):
        # Emit RUN_STARTED event
        await ctx.log_event(RunEvent.run_started(run_id, feed.name))

        try:
            async for candidate in feed.fetch():
                stats.processed += 1
                try:
                    result = await process_candidate(ctx, candidate, source=feed.name)
                    if result.action == ProcessAction.CREATED:
                        stats.new += 1
                        await ctx.log_event(
                            RunEvent.record_created(
                                run_id=run_id,
                                feed_name=feed.name,
                                natural_key=result.record.natural_key,
                                record_id=result.record.id,
                            )
                        )
                    elif result.action == ProcessAction.UPDATED:
                        stats.updated += 1
                        await ctx.log_event(
                            RunEvent.record_updated(
                                run_id=run_id,
                                feed_name=feed.name,
                                natural_key=result.record.natural_key,
                                record_id=result.record.id,
                                previous_hash=result.previous_content_hash,
                                new_hash=result.record.content_hash,
                                version=result.record.content_version,
                            )
                        )
                    else:  # DUPLICATE
                        stats.duplicates += 1
                        await ctx.log_event(
                            RunEvent.record_duplicate(
                                run_id=run_id,
                                feed_name=feed.name,
                                natural_key=result.record.natural_key,
                                record_id=result.record.id,
                            )
                        )
                except FeedSpineError:
                    stats.errors += 1
                    logger.exception(
                        "Feed error processing candidate %s",
                        getattr(candidate, "natural_key", "<unknown>"),
                    )
                except Exception:
                    stats.errors += 1
                    logger.exception(
                        "Unexpected error processing candidate %s",
                        getattr(candidate, "natural_key", "<unknown>"),
                    )

            stats.duration_ms = (time.perf_counter() - start_time) * 1000

            # Emit RUN_COMPLETED event
            await ctx.log_event(
                RunEvent.run_completed(
                    run_id=run_id,
                    feed_name=feed.name,
                    processed=stats.processed,
                    new=stats.new,
                    updated=stats.updated,
                    duplicates=stats.duplicates,
                    errors=stats.errors,
                    duration_ms=stats.duration_ms,
                )
            )

        except Exception as e:
            # Emit RUN_ERROR event
            await ctx.log_event(
                RunEvent.run_error(
                    run_id=run_id,
                    feed_name=feed.name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
            )
            raise

    return stats
