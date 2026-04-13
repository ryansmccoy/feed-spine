"""Registration helpers — translate domain concepts to spine-core config.

Provides convenience functions that create spine-core schedule and
event-rule entries for feed-spine workflows without requiring callers
to know the underlying schema details.
"""

from __future__ import annotations

import json
from typing import Any

from feedspine._vendor.ports import EventRuleStore, ScheduleStore


def register_feed(
    schedule_store: ScheduleStore,
    feed_name: str,
    *,
    cron_expression: str = "*/15 * * * *",
    priority: int = 100,
    enabled: bool = True,
) -> str:
    """Register a feed for scheduled collection.

    Creates a spine-core Schedule that produces WorkItems with
    ``workflow="feed.collect"`` at the given interval.

    Args:
        schedule_store: spine-core schedule store.
        feed_name: Unique feed adapter name.
        cron_expression: Cron expression for collection frequency.
        priority: Schedule priority (higher = more important).
        enabled: Whether the schedule starts enabled.

    Returns:
        The created schedule ID.
    """
    return schedule_store.create(
        {
            "name": f"feed-collect:{feed_name}",
            "target_type": "workflow",
            "target_name": "feed.collect",
            "params": json.dumps({"feed_name": feed_name}),
            "cron_expression": cron_expression,
            "priority": priority,
            "enabled": enabled,
            "dispatch_type": "agent",
            "dispatch_target": "feed.collect",
        }
    )


def register_enrichment_on_collection(
    event_rule_store: EventRuleStore,
    feed_name: str,
    enricher_name: str,
    *,
    enabled: bool = True,
) -> str:
    """Register an event rule: collection → enrichment chaining.

    When ``feed.collection.completed`` fires for the given feed,
    the event rule will trigger a CALLBACK that creates enrichment
    work items for the new records.

    Args:
        event_rule_store: spine-core event rule store.
        feed_name: Feed name to filter on.
        enricher_name: Enricher to run on new records.
        enabled: Whether the rule starts enabled.

    Returns:
        The created rule ID.
    """
    callback_name = f"enrich-on-collect:{feed_name}:{enricher_name}"
    return event_rule_store.create(
        {
            "name": callback_name,
            "event_pattern": "feed.collection.completed",
            "source_filter": feed_name,
            "action": "CALLBACK",
            "callback_name": callback_name,
            "enabled": enabled,
        }
    )


def enrichment_callback_factory(
    work_item_store: Any,
    storage: Any,
    enricher_name: str,
    *,
    source_layer: str = "BRONZE",
    target_layer: str = "SILVER",
    limit: int = 500,
) -> Any:
    """Build an EventDecider callback handler for enrichment fanout.

    The returned callable receives a ``feed.collection.completed`` event
    and creates one WorkItem per record for the given enricher.

    Args:
        work_item_store: spine-core work-item store.
        storage: StorageBackend for querying records.
        enricher_name: Enricher to run.
        source_layer: Layer to query records from.
        target_layer: Target layer after enrichment.
        limit: Max records to enrich per event.

    Returns:
        Callback handler compatible with ``EventDecider.register_callback``.
    """
    from feedspine._vendor.ports import WorkItemCreate
    from feedspine.enricher.batch import create_enrichment_work_items
    from feedspine.models.base import Layer

    {l.value.upper(): l for l in Layer}

    def handler(event: dict) -> list[WorkItemCreate]:
        # Use record_ids from event payload if available
        data = event.get("data") or event.get("payload") or {}
        record_ids = data.get("record_ids", [])

        if not record_ids:
            # Fallback: nothing to do (caller didn't include record_ids)
            return []

        _batch_id, _item_ids = create_enrichment_work_items(
            work_item_store,
            enricher_name,
            record_ids,
            source_layer=source_layer,
            target_layer=target_layer,
        )
        # WorkItems are already persisted by create_enrichment_work_items.
        # Return empty — the batch creator writes directly to the store.
        return []

    return handler
