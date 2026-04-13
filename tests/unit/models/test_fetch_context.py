"""Tests for FetchContext model."""

from feedspine.models.fetch_context import FetchContext


class TestFetchContext:
    """Test FetchContext dataclass."""

    def test_basic_creation(self):
        """FetchContext can be created with endpoint_url."""
        ctx = FetchContext(endpoint_url="https://api.example.com/feed")

        assert ctx.endpoint_url == "https://api.example.com/feed"
        assert ctx.etag is None
        assert ctx.last_modified is None
        assert ctx.consecutive_failures == 0
        assert ctx.total_fetches == 0

    def test_make_conditional_headers_empty(self):
        """No headers when no ETag/Last-Modified."""
        ctx = FetchContext(endpoint_url="https://example.com")
        headers = ctx.make_conditional_headers()

        assert headers == {}

    def test_make_conditional_headers_with_etag(self):
        """If-None-Match header from ETag."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            etag='"abc123"',
        )
        headers = ctx.make_conditional_headers()

        assert headers["If-None-Match"] == '"abc123"'
        assert "If-Modified-Since" not in headers

    def test_make_conditional_headers_with_last_modified(self):
        """If-Modified-Since header from Last-Modified."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            last_modified="Wed, 15 Jan 2026 10:30:00 GMT",
        )
        headers = ctx.make_conditional_headers()

        assert headers["If-Modified-Since"] == "Wed, 15 Jan 2026 10:30:00 GMT"
        assert "If-None-Match" not in headers

    def test_make_conditional_headers_with_both(self):
        """Both headers when both values present."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            etag='"xyz789"',
            last_modified="Wed, 15 Jan 2026 10:30:00 GMT",
        )
        headers = ctx.make_conditional_headers()

        assert headers["If-None-Match"] == '"xyz789"'
        assert headers["If-Modified-Since"] == "Wed, 15 Jan 2026 10:30:00 GMT"

    def test_update_from_response_success_with_content(self):
        """update_from_response on 200 with new content."""
        ctx = FetchContext(endpoint_url="https://example.com")

        updated = ctx.update_from_response(
            status=200,
            etag='"new-etag"',
            last_modified="Thu, 16 Jan 2026 12:00:00 GMT",
        )

        assert updated.etag == '"new-etag"'
        assert updated.last_modified == "Thu, 16 Jan 2026 12:00:00 GMT"
        assert updated.http_status == 200
        assert updated.total_fetches == 1
        assert updated.total_304s == 0
        assert updated.consecutive_failures == 0
        assert updated.last_fetch_at is not None
        assert updated.last_success_at is not None

    def test_update_from_response_304_not_modified(self):
        """update_from_response on 304 increments 304 counter."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            etag='"existing"',
            total_304s=5,
        )

        updated = ctx.update_from_response(
            status=304,
            etag=None,  # No change
            last_modified=None,
        )

        assert updated.etag == '"existing"'  # Preserved
        assert updated.http_status == 304
        assert updated.total_fetches == 1
        assert updated.total_304s == 6  # Incremented
        assert updated.consecutive_failures == 0

    def test_record_failure(self):
        """record_failure increments failure counter."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            consecutive_failures=2,
        )

        updated = ctx.record_failure()

        assert updated.consecutive_failures == 3
        assert updated.total_fetches == 1
        assert updated.http_status is None  # Error, no status

    def test_is_healthy_property(self):
        """is_healthy based on failure count."""
        healthy = FetchContext(
            endpoint_url="https://example.com",
            consecutive_failures=2,
        )
        unhealthy = FetchContext(
            endpoint_url="https://example.com",
            consecutive_failures=5,
        )

        assert healthy.is_healthy is True  # < 5 failures
        assert unhealthy.is_healthy is False  # >= 5 failures

    def test_to_dict_serialization(self):
        """to_dict serializes all fields."""
        ctx = FetchContext(
            endpoint_url="https://example.com",
            etag='"abc"',
            last_modified="Wed, 15 Jan 2026",
            consecutive_failures=1,
            total_fetches=10,
            total_304s=5,
        )

        d = ctx.to_dict()

        assert d["endpoint_url"] == "https://example.com"
        assert d["etag"] == '"abc"'
        assert d["last_modified"] == "Wed, 15 Jan 2026"
        assert d["consecutive_failures"] == 1
        assert d["total_fetches"] == 10
        assert d["total_304s"] == 5

    def test_from_dict_deserialization(self):
        """from_dict deserializes correctly."""
        data = {
            "endpoint_url": "https://api.example.com",
            "etag": '"xyz"',
            "last_modified": "Thu, 16 Jan 2026",
            "last_fetch_at": "2026-01-16T10:00:00+00:00",
            "consecutive_failures": 0,
            "total_fetches": 50,
            "total_304s": 25,
            "http_status": 200,
        }

        ctx = FetchContext.from_dict(data)

        assert ctx.endpoint_url == "https://api.example.com"
        assert ctx.etag == '"xyz"'
        assert ctx.total_304s == 25
        assert ctx.http_status == 200


class TestFetchContextImmutability:
    """Test that FetchContext updates create new instances."""

    def test_update_from_response_creates_new_instance(self):
        """update_from_response should not mutate original."""
        original = FetchContext(
            endpoint_url="https://example.com",
            etag='"old"',
        )

        updated = original.update_from_response(
            status=200,
            etag='"new"',
            last_modified=None,
        )

        assert original.etag == '"old"'  # Original unchanged
        assert updated.etag == '"new"'  # New instance has new value
        assert original is not updated

    def test_record_failure_creates_new_instance(self):
        """record_failure should not mutate original."""
        original = FetchContext(
            endpoint_url="https://example.com",
            consecutive_failures=0,
        )

        updated = original.record_failure()

        assert original.consecutive_failures == 0
        assert updated.consecutive_failures == 1
        assert original is not updated
