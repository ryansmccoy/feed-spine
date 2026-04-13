"""Tests for feedspine.types module — NewType identifiers (CS-14)."""

from __future__ import annotations

from feedspine.types import FeedName, JobId, RecordId, SourceId


class TestNewTypes:
    """NewType wrappers are str at runtime but distinct for type checkers."""

    def test_feed_name_is_str(self):
        name = FeedName("sec-rss")
        assert isinstance(name, str)
        assert name == "sec-rss"

    def test_record_id_is_str(self):
        rid = RecordId("abc-123")
        assert isinstance(rid, str)

    def test_source_id_is_str(self):
        sid = SourceId("src-001")
        assert isinstance(sid, str)

    def test_job_id_is_str(self):
        jid = JobId("job-42")
        assert isinstance(jid, str)

    def test_types_are_distinct_callables(self):
        """Each NewType is a distinct callable, not the same object."""
        assert FeedName is not RecordId
        assert RecordId is not JobId
        assert JobId is not SourceId

    def test_usable_as_dict_keys(self):
        d: dict[FeedName, int] = {FeedName("a"): 1, FeedName("b"): 2}
        assert d[FeedName("a")] == 1

    def test_string_operations_preserve_type(self):
        name = FeedName("sec-rss")
        assert name.upper() == "SEC-RSS"
        assert name.startswith("sec")
