"""Adapter-layer test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.adapter.base import BaseFeedAdapter
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate


class StubAdapter(BaseFeedAdapter):
    """Minimal adapter for testing."""

    def __init__(self, name: str = "stub", items: list[dict] | None = None):
        super().__init__(name=name)
        self._items = items or []

    async def _fetch_items(self) -> list[dict]:
        return self._items

    def _to_candidate(self, item: dict) -> RecordCandidate:
        return RecordCandidate(
            natural_key=item.get("id", "unknown"),
            published_at=datetime.now(UTC),
            content=item,
            metadata=Metadata(source=self.name),
        )


@pytest.fixture
def stub_adapter():
    """Stub adapter with no items."""
    return StubAdapter()


@pytest.fixture
def stub_adapter_with_data():
    """Stub adapter with sample items."""
    return StubAdapter(
        items=[
            {"id": "item-001", "title": "First"},
            {"id": "item-002", "title": "Second"},
        ]
    )
