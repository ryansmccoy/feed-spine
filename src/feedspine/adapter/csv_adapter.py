"""CSV file feed adapter.

Concrete implementation of :class:`FileFeedAdapter` for CSV / TSV files
stored locally or fetched via HTTP.

Example:
    >>> from feedspine.adapter.csv import CSVFeedAdapter
    >>> adapter = CSVFeedAdapter(
    ...     path="/data/prices.csv",
    ...     name="prices",
    ...     key_column="ticker",
    ... )
    >>> adapter.name
    'prices'
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from feedspine.adapter.file import FileFeedAdapter
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate


class CSVFeedAdapter(FileFeedAdapter):
    """Feed adapter for local or remote CSV / TSV files.

    Reads a CSV file (local path or HTTP URL), parses rows into dicts,
    and yields a :class:`RecordCandidate` per row.  De-duplication is
    keyed by ``key_column`` (or a composite of ``key_columns``).

    When ``emit_only_new=True`` (default *False*), only rows whose
    content hash differs from the previous snapshot are emitted.

    Args:
        path: Local file path or HTTP(S) URL.
        name: Adapter identifier.
        key_column: Column name whose value becomes the ``natural_key``.
            Mutually exclusive with *key_columns*.
        key_columns: Multiple columns joined with ``|`` as the key.
        delimiter: Field delimiter (default: auto-detect ``,`` or ``\\t``).
        source_type: Metadata source type (default: ``"csv"``).
        encoding: File encoding (default: ``"utf-8"``).
        emit_only_new: Only yield changed rows (requires snapshot tracking).
        requests_per_second: Rate limit for HTTP fetches.

    Example:
        >>> adapter = CSVFeedAdapter(
        ...     path="data/filings.csv",
        ...     name="sec-filings",
        ...     key_column="accession_number",
        ...     source_type="sec.filings",
        ... )
    """

    def __init__(
        self,
        path: str,
        name: str,
        *,
        key_column: str | None = None,
        key_columns: list[str] | None = None,
        delimiter: str | None = None,
        source_type: str = "csv",
        encoding: str = "utf-8",
        emit_only_new: bool = False,
        requests_per_second: float = 5.0,
    ) -> None:
        super().__init__(
            name=name,
            source_url=path if path.startswith(("http://", "https://")) else None,
            emit_only_new=emit_only_new,
        )
        self._path = path
        self._key_column = key_column
        self._key_columns = key_columns or []
        self._delimiter = delimiter
        self._source_type = source_type
        self._encoding = encoding

        if not key_column and not key_columns:
            msg = "Either key_column or key_columns must be specified"
            raise ValueError(msg)

    async def _fetch_file(self) -> bytes:
        """Read the CSV from disk or download via HTTP."""
        if self._path.startswith(("http://", "https://")):
            import httpx

            from feedspine.core.config import get_settings

            async with httpx.AsyncClient(timeout=get_settings().adapter_timeout) as client:
                resp = await client.get(self._path)
                resp.raise_for_status()
                return resp.content
        else:
            from pathlib import Path

            return Path(self._path).read_bytes()

    async def _parse_file(self, content: bytes) -> AsyncIterator[dict[str, Any]]:
        """Parse CSV bytes into row dicts."""
        text = content.decode(self._encoding, errors="replace")
        delimiter = self._delimiter or self._detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            yield row

    def _row_to_candidate(self, row: dict[str, Any], index: int = 0) -> RecordCandidate:
        """Convert a CSV row dict to a RecordCandidate."""
        # Build natural key
        if self._key_column:
            key = str(row.get(self._key_column, ""))
        else:
            key = "|".join(str(row.get(c, "")) for c in self._key_columns)

        if not key.strip():
            key = f"row-{hash(tuple(sorted(row.items())))}"

        # Try to extract a timestamp from the row
        published_at = self._extract_date(row)

        return RecordCandidate(
            natural_key=f"{self._name}:{key}",
            published_at=published_at,
            content=dict(row),
            metadata=Metadata(
                source=self._name,
                source_type=self._source_type,
                extra={"file": self._path},
            ),
        )

    @staticmethod
    def _detect_delimiter(text: str) -> str:
        """Auto-detect CSV vs TSV based on first line."""
        first_line = text.split("\n", 1)[0]
        if "\t" in first_line:
            return "\t"
        return ","

    @staticmethod
    def _extract_date(row: dict[str, Any]) -> datetime:
        """Try to parse a date from common column names."""
        for col in ("date", "Date", "DATE", "timestamp", "published", "filed", "created_at"):
            val = row.get(col)
            if val:
                for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%Y%m%d"):
                    try:
                        return datetime.strptime(str(val), fmt).replace(tzinfo=UTC)
                    except ValueError:
                        continue
        return datetime.now(UTC)
