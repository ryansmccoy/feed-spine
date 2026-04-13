"""Tests for feedspine.adapter.json - JSON API feed adapter."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from feedspine.adapter.base import FeedAdapter, FeedError
from feedspine.models.record import RecordCandidate

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_json_array() -> str:
    """Sample JSON array response."""
    return json.dumps(
        [
            {
                "id": "item-001",
                "title": "First Item",
                "url": "https://example.com/item/1",
                "published": "2026-01-01T12:00:00Z",
                "summary": "First item summary",
            },
            {
                "id": "item-002",
                "title": "Second Item",
                "url": "https://example.com/item/2",
                "published": "2026-01-02T12:00:00Z",
                "summary": "Second item summary",
            },
        ]
    )


@pytest.fixture
def sample_json_nested() -> str:
    """Sample JSON with nested items."""
    return json.dumps(
        {
            "status": "ok",
            "count": 2,
            "data": {
                "items": [
                    {"id": "nested-001", "title": "Nested Item 1"},
                    {"id": "nested-002", "title": "Nested Item 2"},
                ]
            },
        }
    )


@pytest.fixture
def sample_json_paginated() -> str:
    """Sample JSON with pagination info."""
    return json.dumps(
        {
            "results": [
                {"id": "page-001", "title": "Page Item 1"},
            ],
            "next_page": "https://api.example.com/items?page=2",
            "total": 100,
        }
    )


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestJSONAdapterProtocol:
    """Tests for FeedAdapter protocol compliance."""

    async def test_implements_feed_adapter_protocol(self) -> None:
        """JSONFeedAdapter implements FeedAdapter protocol."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")
        assert isinstance(adapter, FeedAdapter)

    async def test_has_required_name_property(self) -> None:
        """Adapter has name property."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="my-api")
        assert adapter.name == "my-api"

    async def test_has_fetch_method(self) -> None:
        """Adapter has async fetch method."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")
        assert hasattr(adapter, "fetch")
        assert callable(adapter.fetch)


# =============================================================================
# Creation Tests
# =============================================================================


class TestJSONAdapterCreation:
    """Tests for JSONFeedAdapter instantiation."""

    async def test_create_with_url_and_name(self) -> None:
        """Create adapter with required parameters."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="example-api",
        )
        assert adapter.url == "https://api.example.com/items"
        assert adapter.name == "example-api"

    async def test_create_with_custom_source_type(self) -> None:
        """Create adapter with custom source type."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            source_type="api.custom",
        )
        assert adapter.source_type == "api.custom"

    async def test_default_source_type_is_json(self) -> None:
        """Default source type is 'json'."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
        )
        assert adapter.source_type == "json"

    async def test_create_with_headers(self) -> None:
        """Create adapter with custom HTTP headers."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            headers={"Authorization": "Bearer token123"},
        )
        assert adapter.headers == {"Authorization": "Bearer token123"}

    async def test_create_with_items_path(self) -> None:
        """Create adapter with JSONPath to items."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            items_path="data.items",
        )
        assert adapter.items_path == "data.items"


# =============================================================================
# Field Mapping Tests
# =============================================================================


class TestJSONAdapterFieldMapping:
    """Tests for field mapping configuration."""

    async def test_default_field_mapping(self) -> None:
        """Default field mapping uses standard names."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
        )
        # Default mapping should include id, title, url, published_at
        assert "id" in adapter.field_mapping
        assert "title" in adapter.field_mapping

    async def test_custom_field_mapping(self) -> None:
        """Create adapter with custom field mapping."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            field_mapping={
                "id": "item_id",
                "title": "headline",
                "url": "link",
                "published_at": "created_at",
            },
        )
        assert adapter.field_mapping["id"] == "item_id"
        assert adapter.field_mapping["title"] == "headline"


# =============================================================================
# Fetch Tests (with mocked HTTP)
# =============================================================================


class TestJSONAdapterFetch:
    """Tests for fetching and parsing JSON feeds."""

    async def test_fetch_parses_json_array(self, sample_json_array: str) -> None:
        """Fetch returns RecordCandidates from JSON array."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
        )

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 2
        assert all(isinstance(c, RecordCandidate) for c in candidates)

    async def test_fetch_extracts_title(self, sample_json_array: str) -> None:
        """Fetch extracts title from JSON items."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].content.get("title") == "First Item"
        assert candidates[1].content.get("title") == "Second Item"

    async def test_fetch_uses_id_as_natural_key(self, sample_json_array: str) -> None:
        """Fetch uses id field as natural key."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].natural_key == "item-001"
        assert candidates[1].natural_key == "item-002"

    async def test_fetch_parses_published_date(self, sample_json_array: str) -> None:
        """Fetch parses published date into published_at."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].published_at is not None
        assert candidates[0].published_at.year == 2026

    async def test_fetch_sets_metadata_source(self, sample_json_array: str) -> None:
        """Fetch sets metadata source to adapter name."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="my-api")

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].metadata.source == "my-api"


# =============================================================================
# Nested JSON Tests
# =============================================================================


class TestJSONAdapterNested:
    """Tests for nested JSON structures."""

    async def test_fetch_with_items_path(self, sample_json_nested: str) -> None:
        """Fetch extracts items from nested path."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            items_path="data.items",
        )

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_nested)):
            candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 2
        assert candidates[0].content.get("title") == "Nested Item 1"

    async def test_fetch_with_dot_notation_path(self, sample_json_nested: str) -> None:
        """Fetch handles dot notation for nested paths."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            items_path="data.items",
        )

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_nested)):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].natural_key == "nested-001"


# =============================================================================
# Custom Field Mapping Tests
# =============================================================================


class TestJSONAdapterCustomMapping:
    """Tests for custom field mapping."""

    async def test_custom_id_field(self) -> None:
        """Fetch uses custom id field as natural key."""
        from feedspine.adapter.json import JSONFeedAdapter

        data = [{"item_id": "custom-001", "headline": "Custom Title"}]

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            field_mapping={
                "id": "item_id",
                "title": "headline",
            },
        )

        with patch.object(adapter, "_fetch_json", return_value=data):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].natural_key == "custom-001"
        assert candidates[0].content.get("title") == "Custom Title"

    async def test_custom_date_field(self) -> None:
        """Fetch uses custom date field."""
        from feedspine.adapter.json import JSONFeedAdapter

        data = [{"id": "001", "created_at": "2026-01-15T10:00:00Z"}]

        adapter = JSONFeedAdapter(
            url="https://api.example.com/items",
            name="test",
            field_mapping={"published_at": "created_at"},
        )

        with patch.object(adapter, "_fetch_json", return_value=data):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].published_at is not None
        assert candidates[0].published_at.day == 15


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestJSONAdapterErrors:
    """Tests for error handling."""

    async def test_network_error_raises_feed_error(self) -> None:
        """Network errors are wrapped in FeedError."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        with (
            patch.object(
                adapter,
                "_fetch_json",
                side_effect=ConnectionError("Failed to connect"),
            ),
            pytest.raises(FeedError) as exc_info,
        ):
            _ = [c async for c in adapter.fetch()]

        assert exc_info.value.source == "test"

    async def test_invalid_json_raises_feed_error(self) -> None:
        """Invalid JSON raises FeedError."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        # _fetch_json should handle JSON parsing, return raw response here
        with (
            patch.object(
                adapter,
                "_fetch_json",
                side_effect=json.JSONDecodeError("Invalid", "", 0),
            ),
            pytest.raises(FeedError),
        ):
            _ = [c async for c in adapter.fetch()]

    async def test_empty_response_returns_no_candidates(self) -> None:
        """Empty JSON array returns empty iterator."""
        from feedspine.adapter.json import JSONFeedAdapter

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")

        with patch.object(adapter, "_fetch_json", return_value=[]):
            candidates = [c async for c in adapter.fetch()]

        assert candidates == []


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestJSONAdapterLifecycle:
    """Tests for adapter lifecycle management."""

    async def test_context_manager_support(self) -> None:
        """Adapter works as async context manager."""
        from feedspine.adapter.json import JSONFeedAdapter

        async with JSONFeedAdapter(url="https://api.example.com/items", name="test") as adapter:
            assert adapter.name == "test"


# =============================================================================
# Pipeline Integration Test
# =============================================================================


class TestJSONAdapterPipelineIntegration:
    """Tests for integration with Pipeline."""

    async def test_works_with_pipeline(self, sample_json_array: str) -> None:
        """JSONFeedAdapter works with Pipeline.run()."""
        from feedspine.adapter.json import JSONFeedAdapter
        from feedspine.pipeline import Pipeline
        from feedspine.storage.memory import MemoryStorage

        storage = MemoryStorage()
        await storage.initialize()

        adapter = JSONFeedAdapter(url="https://api.example.com/items", name="test")
        pipeline = Pipeline(storage=storage)

        with patch.object(adapter, "_fetch_json", return_value=json.loads(sample_json_array)):
            stats = await pipeline.run(adapter)

        assert stats.processed == 2
        assert stats.new == 2
        assert await storage.count() == 2
