"""Tests for FeedSpineSettings."""

from __future__ import annotations

import pytest

pytest.importorskip("spine", reason="spine-core not installed")

from feedspine.core.config import FeedSpineSettings


class TestFeedSpineSettings:
    """Test FeedSpineSettings defaults and inheritance."""

    def test_defaults(self):
        s = FeedSpineSettings(_env_file=None)
        assert s.port == 11300
        assert s.storage == "memory"
        assert s.otel_service_name == "feed-spine"
        assert s.require_auth is False
        assert s.api_key is None

    def test_inherits_spine_base(self):
        from spine.core.settings import SpineBaseSettings

        assert issubclass(FeedSpineSettings, SpineBaseSettings)

    def test_cors_origins_list(self):
        s = FeedSpineSettings(cors_origins="http://a.com, http://b.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_cors_origins_list_empty(self):
        s = FeedSpineSettings(cors_origins="")
        assert s.cors_origins_list == []

    def test_env_prefix(self, monkeypatch):
        monkeypatch.setenv("FEEDSPINE_PORT", "9999")
        monkeypatch.setenv("FEEDSPINE_STORAGE", "postgresql")
        s = FeedSpineSettings()
        assert s.port == 9999
        assert s.storage == "postgresql"

    def test_settings_alias(self):
        from feedspine.core.config import Settings

        assert Settings is FeedSpineSettings

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("fastapi"),
        reason="fastapi not installed",
    )
    def test_api_settings_reexport(self):
        from feedspine.api.settings import APISettings

        assert APISettings is FeedSpineSettings
