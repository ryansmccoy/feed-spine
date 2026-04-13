"""FeedEnrichmentWorker — executor for feed.enrich work items.

A spine-core Executor that receives dispatched work items.
It loads the record from storage, runs the enricher, and returns
a DispatchResult containing success/failure status and enrichment stats.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from spine.core.logging import get_logger
from spine.ports.executor import DispatchResult

if TYPE_CHECKING:
    from spine.ports.dispatch_config import DispatchConfig

    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.storage import StorageBackend

logger = get_logger(__name__)


class FeedEnrichmentWorker:
    """Executor for ``feed.enrich`` work items.

    Each dispatched item contains a ``record_id`` and ``enricher`` name.
    The executor loads the record, runs the enricher, stores the result,
    and returns a DispatchResult.

    Args:
        storage: Domain record storage (load/save records).
        enricher_registry: Mapping of enricher name → Enricher instance.
    """

    def __init__(
        self,
        storage: StorageBackend,
        enricher_registry: dict[str, Enricher],
    ) -> None:
        self._storage = storage
        self._enrichers = enricher_registry

    async def dispatch(
        self, config: DispatchConfig, work_item: dict[str, Any], *, timeout: int = 300
    ) -> DispatchResult:
        """Process a single dispatched work item.

        Args:
            config: Dispatch configuration (from the work item).
            work_item: The work item payload containing params.
            timeout: Maximum execution time in seconds.
        """
        start_time = time.monotonic()
        item_id = work_item.get("id")

        params = work_item.get("params_json")
        if isinstance(params, str):
            params = json.loads(params)
        elif params is None:
            params = {}

        record_id: str = params.get("record_id")
        enricher_name: str = params.get("enricher")

        if not record_id or not enricher_name:
            return DispatchResult(success=False, error="Missing record_id or enricher in params")

        enricher = self._enrichers.get(enricher_name)
        if enricher is None:
            return DispatchResult(
                success=False,
                error=f"Unknown enricher: {enricher_name}",
            )

        try:
            record = await self._storage.get(record_id)
            if record is None:
                return DispatchResult(
                    success=False,
                    error=f"Record not found: {record_id}",
                )

            result = await asyncio.wait_for(enricher.enrich(record), timeout=timeout)

            from feedspine.protocols.enricher import EnrichmentStatus

            if result.status in (
                EnrichmentStatus.SUCCESS,
                EnrichmentStatus.SKIPPED,
            ):
                if result.status == EnrichmentStatus.SUCCESS:
                    await self._storage.store(record)

                duration_ms = (
                    result.duration_ms
                    if result.duration_ms is not None
                    else int((time.monotonic() - start_time) * 1000)
                )

                response_body = json.dumps(
                    {
                        "status": result.status.value,
                        "enricher": result.enricher_name,
                        "record_id": result.record_id,
                        "fields_added": result.fields_added,
                        "fields_updated": result.fields_updated,
                        "duration_ms": duration_ms,
                    }
                )

                return DispatchResult(
                    success=True,
                    status_code=200,
                    response_body=response_body,
                    duration_ms=duration_ms,
                )
            else:
                return DispatchResult(
                    success=False,
                    error=result.error_message or f"Enrichment {result.status.value}",
                )
        except TimeoutError:
            logger.warning(
                "Enrichment timed out after %.1fs for item %s (record %s, enricher %s)",
                timeout,
                item_id,
                record_id,
                enricher_name,
            )
            return DispatchResult(
                success=False,
                error=f"Enrichment timed out after {timeout}s (item={item_id}, enricher={enricher_name})",
            )
        except Exception as e:
            logger.exception(
                "Enrichment failed for item %s (record %s, enricher %s)",
                item_id,
                record_id,
                enricher_name,
            )
            return DispatchResult(
                success=False,
                error=f"Unhandled exception: {e!s}",
            )
