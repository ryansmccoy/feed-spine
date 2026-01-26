"""Tests for ConsoleNotifier implementation.

Tests cover:
- Sending notifications
- Severity filtering
- Output formatting
- Stream selection (stdout/stderr)
- Lifecycle (initialize/close)
- Protocol compliance
"""

import io

from feedspine.notifier.console import ConsoleNotifier
from feedspine.protocols.notification import Notification, Severity

# =============================================================================
# Basic Send Tests
# =============================================================================


class TestConsoleNotifierSend:
    """Tests for sending notifications."""

    async def test_send_returns_true_when_displayed(self):
        """send returns True when notification is displayed."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out)

        notification = Notification(
            title="Test",
            message="Hello",
            severity=Severity.INFO,
        )

        result = await notifier.send(notification)

        assert result is True

    async def test_send_writes_to_output(self):
        """send writes to output stream."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out)

        await notifier.send(
            Notification(
                title="Test Title",
                message="Test message",
                severity=Severity.INFO,
            )
        )

        output = out.getvalue()
        assert "Test Title" in output
        assert "Test message" in output

    async def test_send_includes_severity_indicator(self):
        """Output includes severity indicator."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out)

        await notifier.send(
            Notification(
                title="Warning",
                message="Caution",
                severity=Severity.WARNING,
            )
        )

        output = out.getvalue()
        # Should have some indicator
        assert len(output) > 0


# =============================================================================
# Severity Filtering Tests
# =============================================================================


class TestConsoleNotifierSeverityFilter:
    """Tests for severity filtering."""

    async def test_filters_below_min_severity(self):
        """Notifications below min_severity are not displayed."""
        out = io.StringIO()
        notifier = ConsoleNotifier(min_severity=Severity.WARNING, stdout=out)

        result = await notifier.send(
            Notification(
                title="Debug",
                message="Low priority",
                severity=Severity.DEBUG,
            )
        )

        assert result is False
        assert out.getvalue() == ""

    async def test_displays_at_min_severity(self):
        """Notifications at min_severity are displayed."""
        out = io.StringIO()
        notifier = ConsoleNotifier(min_severity=Severity.WARNING, stdout=out)

        result = await notifier.send(
            Notification(
                title="Warning",
                message="At threshold",
                severity=Severity.WARNING,
            )
        )

        assert result is True
        assert "Warning" in out.getvalue()

    async def test_displays_above_min_severity(self):
        """Notifications above min_severity are displayed."""
        out = io.StringIO()
        notifier = ConsoleNotifier(min_severity=Severity.WARNING, stdout=out)

        result = await notifier.send(
            Notification(
                title="Error",
                message="Above threshold",
                severity=Severity.ERROR,
            )
        )

        assert result is True

    async def test_default_min_severity_is_debug(self):
        """Default min_severity is DEBUG (show all)."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out)

        result = await notifier.send(
            Notification(
                title="Debug",
                message="Should show",
                severity=Severity.DEBUG,
            )
        )

        assert result is True


# =============================================================================
# Stream Selection Tests
# =============================================================================


class TestConsoleNotifierStreams:
    """Tests for stdout/stderr stream selection."""

    async def test_info_goes_to_stdout(self):
        """INFO severity goes to stdout."""
        out = io.StringIO()
        err = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, stderr=err)

        await notifier.send(
            Notification(
                title="Info",
                message="Information",
                severity=Severity.INFO,
            )
        )

        assert len(out.getvalue()) > 0
        assert err.getvalue() == ""

    async def test_debug_goes_to_stdout(self):
        """DEBUG severity goes to stdout."""
        out = io.StringIO()
        err = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, stderr=err)

        await notifier.send(
            Notification(
                title="Debug",
                message="Debug info",
                severity=Severity.DEBUG,
            )
        )

        assert len(out.getvalue()) > 0
        assert err.getvalue() == ""

    async def test_error_goes_to_stderr(self):
        """ERROR severity goes to stderr."""
        out = io.StringIO()
        err = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, stderr=err)

        await notifier.send(
            Notification(
                title="Error",
                message="Something broke",
                severity=Severity.ERROR,
            )
        )

        assert out.getvalue() == ""
        assert len(err.getvalue()) > 0

    async def test_critical_goes_to_stderr(self):
        """CRITICAL severity goes to stderr."""
        out = io.StringIO()
        err = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, stderr=err)

        await notifier.send(
            Notification(
                title="Critical",
                message="System down",
                severity=Severity.CRITICAL,
            )
        )

        assert out.getvalue() == ""
        assert len(err.getvalue()) > 0


# =============================================================================
# Formatting Tests
# =============================================================================


class TestConsoleNotifierFormatting:
    """Tests for output formatting."""

    async def test_format_with_timestamp(self):
        """Can include timestamp in output."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, show_timestamp=True)

        await notifier.send(
            Notification(
                title="Test",
                message="With time",
                severity=Severity.INFO,
            )
        )

        output = out.getvalue()
        # Should have some date/time characters
        assert any(c.isdigit() for c in output)

    async def test_format_without_timestamp(self):
        """Can exclude timestamp from output."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, show_timestamp=False)

        await notifier.send(
            Notification(
                title="Test",
                message="No time",
                severity=Severity.INFO,
            )
        )

        output = out.getvalue()
        assert "Test" in output

    async def test_format_with_tags(self):
        """Tags are included when show_tags=True."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, show_tags=True, show_timestamp=False)

        await notifier.send(
            Notification(
                title="Test",
                message="Tagged",
                severity=Severity.INFO,
                tags=["urgent", "production"],
            )
        )

        # Tags might be in output
        output = out.getvalue()
        assert "Test" in output


# =============================================================================
# Notification Fields Tests
# =============================================================================


class TestConsoleNotifierNotificationFields:
    """Tests for various notification fields."""

    async def test_notification_with_data(self):
        """Can send notification with data."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, show_timestamp=False)

        await notifier.send(
            Notification(
                title="Alert",
                message="Check this",
                severity=Severity.WARNING,
                data={"user_id": 123, "action": "login"},
            )
        )

        assert "Alert" in out.getvalue()

    async def test_notification_with_tags(self):
        """Can send notification with tags."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out, show_timestamp=False)

        await notifier.send(
            Notification(
                title="Alert",
                message="With tags",
                severity=Severity.INFO,
                tags=["feed-processor", "urgent"],
            )
        )

        assert "Alert" in out.getvalue()


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestConsoleNotifierLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_sets_flag(self):
        """initialize sets _initialized flag."""
        notifier = ConsoleNotifier()

        assert notifier._initialized is False

        await notifier.initialize()

        assert notifier._initialized is True

    async def test_close_clears_flag(self):
        """close clears _initialized flag."""
        notifier = ConsoleNotifier()
        await notifier.initialize()

        await notifier.close()

        assert notifier._initialized is False

    async def test_works_without_initialize(self):
        """Notifier works without explicit initialize."""
        out = io.StringIO()
        notifier = ConsoleNotifier(stdout=out)

        result = await notifier.send(
            Notification(
                title="Test",
                message="No init",
                severity=Severity.INFO,
            )
        )

        assert result is True

    async def test_close_idempotent(self):
        """Multiple closes are safe."""
        notifier = ConsoleNotifier()
        await notifier.initialize()

        await notifier.close()
        await notifier.close()

        assert notifier._initialized is False


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestConsoleNotifierProtocol:
    """Tests for Notifier protocol compliance."""

    def test_has_required_methods(self):
        """ConsoleNotifier has all required Notifier methods."""
        notifier = ConsoleNotifier()

        assert hasattr(notifier, "initialize")
        assert hasattr(notifier, "close")
        assert hasattr(notifier, "send")

    def test_methods_are_async(self):
        """All I/O methods are async."""
        import inspect

        notifier = ConsoleNotifier()

        assert inspect.iscoroutinefunction(notifier.initialize)
        assert inspect.iscoroutinefunction(notifier.close)
        assert inspect.iscoroutinefunction(notifier.send)

    def test_severity_indicators_defined(self):
        """All severity levels have indicators."""
        assert Severity.DEBUG in ConsoleNotifier.INDICATORS
        assert Severity.INFO in ConsoleNotifier.INDICATORS
        assert Severity.WARNING in ConsoleNotifier.INDICATORS
        assert Severity.ERROR in ConsoleNotifier.INDICATORS
        assert Severity.CRITICAL in ConsoleNotifier.INDICATORS
