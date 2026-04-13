"""FeedSpine domain repository — portable CRUD over Records, Sightings, FeedRuns.

Extends :class:`~feedspine.storage.repository.BaseRepository` with
feedspine-specific operations.  All SQL flows through the Dialect
abstraction so the same repository works against both SQLite and
PostgreSQL without code changes.

Composes :class:`~feedspine.storage.feed_queries.FeedQueryMixin` and
:class:`~feedspine.storage.feed_mutations.FeedMutationMixin` for a
clean separation of read and write concerns.
"""

from __future__ import annotations

from feedspine.storage.feed_mutations import FeedMutationMixin
from feedspine.storage.feed_queries import FeedQueryMixin
from feedspine.storage.repository import BaseRepository


class FeedRepository(FeedQueryMixin, FeedMutationMixin, BaseRepository):
    """Domain repository for FeedSpine records, sightings, and feed runs.

    All SQL uses :attr:`dialect` for placeholders, timestamps, and upsert
    syntax, making the same code portable across SQLite and PostgreSQL.

    Composes :class:`~feedspine.storage.feed_queries.FeedQueryMixin` and
    :class:`~feedspine.storage.feed_mutations.FeedMutationMixin` for a
    clean separation of read and write concerns.

    Parameters:
        conn: Connection protocol implementation (sqlite3.Connection,
              SAConnectionBridge, etc.)
        dialect: SQL dialect instance.
    """


__all__ = [
    "FeedRepository",
]
