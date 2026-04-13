"""Schedule operations — CRUD wrapper over spine-core ScheduleStore.

Extends spine-core's ScheduleStore protocol (create, get_by_id, get_due,
advance_next_run) with list, update, and delete operations needed by the
feed-spine API layer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from feedspine._vendor.logging import get_logger

logger = get_logger(__name__)


def list_schedules(
    store: Any,
    *,
    enabled: bool | None = None,
) -> list[dict[str, Any]]:
    """List all schedules, optionally filtered by enabled flag.

    Args:
        store: spine-core ScheduleStore (must have ``_conn`` attribute
            for direct SQL access).
        enabled: If set, filter by enabled state.

    Returns:
        List of schedule dicts.
    """
    conn = store._conn
    if enabled is not None:
        cur = conn.execute(
            "SELECT * FROM core_schedules WHERE enabled = ? ORDER BY created_at DESC",
            (1 if enabled else 0,),
        )
    else:
        cur = conn.execute("SELECT * FROM core_schedules ORDER BY created_at DESC")
    return [dict(r) for r in cur.fetchall()]


def create_schedule(
    store: Any,
    *,
    feed_name: str,
    cron_expression: str = "*/15 * * * *",
    enabled: bool = True,
) -> dict[str, Any]:
    """Create a feed collection schedule via spine-core.

    Args:
        store: spine-core ScheduleStore.
        feed_name: Feed adapter name to schedule.
        cron_expression: Cron expression for collection frequency.
        enabled: Whether the schedule starts enabled.

    Returns:
        The created schedule dict.
    """
    schedule_id = store.create(
        {
            "name": f"feed-collect:{feed_name}",
            "target_type": "workflow",
            "target_name": "feed.collect",
            "params": json.dumps({"feed_name": feed_name}),
            "cron_expression": cron_expression,
            "enabled": enabled,
        }
    )
    return store.get_by_id(schedule_id) or {"id": schedule_id}


def get_schedule(store: Any, schedule_id: str) -> dict[str, Any] | None:
    """Get a schedule by ID.

    Args:
        store: spine-core ScheduleStore.
        schedule_id: Schedule identifier.

    Returns:
        Schedule dict or None.
    """
    return store.get_by_id(schedule_id)


def update_schedule(
    store: Any,
    schedule_id: str,
    *,
    cron_expression: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    """Update a schedule's cron expression or enabled flag.

    Args:
        store: spine-core ScheduleStore (must have ``_conn`` for writes).
        schedule_id: Schedule to update.
        cron_expression: New cron expression (if changing).
        enabled: New enabled state (if changing).

    Returns:
        Updated schedule dict, or None if not found.
    """
    existing = store.get_by_id(schedule_id)
    if existing is None:
        return None

    conn = store._conn
    updates = []
    params: list[Any] = []

    if cron_expression is not None:
        updates.append("cron_expression = ?")
        params.append(cron_expression)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(schedule_id)
        conn.execute(
            f"UPDATE core_schedules SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    return store.get_by_id(schedule_id)


def delete_schedule(store: Any, schedule_id: str) -> bool:
    """Delete a schedule by ID.

    Args:
        store: spine-core ScheduleStore (must have ``_conn`` for writes).
        schedule_id: Schedule to delete.

    Returns:
        True if deleted, False if not found.
    """
    existing = store.get_by_id(schedule_id)
    if existing is None:
        return False

    conn = store._conn
    conn.execute("DELETE FROM core_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    logger.info("Deleted schedule id=%s", schedule_id)
    return True


def list_due_schedules(store: Any) -> list[dict[str, Any]]:
    """List schedules that are due for execution.

    Args:
        store: spine-core ScheduleStore.

    Returns:
        List of due schedule dicts.
    """
    now = datetime.now(UTC).isoformat()
    return store.get_due(now)
