"""SEC EDGAR full-text filing adapter.

Fetches SEC EDGAR filing full-text (10-K, 10-Q, 8-K, etc.) from
the EDGAR full-text search API and the EDGAR archives, yielding
structured :class:`RecordCandidate` objects for each filing.

This adapter complements the RSS adapter (which captures filing
*announcements*) by fetching the actual filing *documents*.

Example:
    >>> from feedspine.adapter.sec_edgar import SECEdgarFilingAdapter
    >>> adapter = SECEdgarFilingAdapter(
    ...     name="sec-10k",
    ...     form_types=["10-K", "10-K/A"],
    ...     cik="0000320193",  # Apple
    ... )
    >>> adapter.name
    'sec-10k'
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
from feedspine._vendor.logging import get_logger

from feedspine.adapter.base import BaseFeedAdapter, FeedError
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate

logger = get_logger(__name__)

# EDGAR EFTS (full-text search) API base
EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"

# EDGAR filing archives base
ARCHIVES_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"

# EDGAR company search API
COMPANY_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# EDGAR submissions API (modern, JSON-based)
SUBMISSIONS_API = "https://data.sec.gov/submissions/CIK{cik}.json"

# Required User-Agent per SEC EDGAR policy
DEFAULT_USER_AGENT = "FeedSpine/1.0 (feedspine@example.com)"


class SECEdgarFilingAdapter(BaseFeedAdapter):
    """Feed adapter for SEC EDGAR filing submissions.

    Uses the EDGAR submissions API to fetch filing metadata (accession
    number, form type, dates, etc.) for a given CIK or ticker.

    For full document text, set ``include_document=True`` to also fetch
    the primary filing document from EDGAR archives.

    Args:
        name: Adapter identifier.
        form_types: Filing types to include (e.g. ``["10-K", "10-Q"]``).
            If *None*, all form types are returned.
        cik: SEC Central Index Key (10-digit, zero-padded).
            Mutually exclusive with *ticker*.
        ticker: Company ticker symbol (resolved to CIK via EDGAR).
            Mutually exclusive with *cik*.
        include_document: Fetch full document text (slower, more data).
        max_filings: Maximum filings to return per fetch (default: 40).
        user_agent: HTTP User-Agent header (SEC requires identification).
        requests_per_second: Rate limit — SEC asks for max 10 req/sec.

    Example:
        >>> adapter = SECEdgarFilingAdapter(
        ...     name="apple-10k",
        ...     form_types=["10-K"],
        ...     ticker="AAPL",
        ... )
    """

    def __init__(
        self,
        name: str = "sec-edgar-filings",
        *,
        form_types: list[str] | None = None,
        cik: str | None = None,
        ticker: str | None = None,
        include_document: bool = False,
        max_filings: int = 40,
        user_agent: str = DEFAULT_USER_AGENT,
        requests_per_second: float = 8.0,
    ) -> None:
        super().__init__(
            name=name,
            source_url="https://www.sec.gov/cgi-bin/browse-edgar",
            requests_per_second=requests_per_second,
        )
        self._form_types = [f.upper() for f in form_types] if form_types else None
        # Normalize CIK to 10-digit zero-padded string
        if cik is not None:
            self._cik = str(cik).lstrip("0").zfill(10)
        else:
            self._cik = None
        self._ticker = ticker
        self._include_document = include_document
        self._max_filings = max_filings
        self._user_agent = user_agent

        if not cik and not ticker:
            msg = "Either cik or ticker must be specified"
            raise ValueError(msg)

    def _build_filing_candidate(
        self,
        *,
        accession: str,
        form_type: str,
        filing_date: str,
        primary_doc: str,
        description: str,
        company_name: str,
        company_tickers: list,
        cik_padded: str,
    ) -> RecordCandidate:
        """Build a RecordCandidate from a single EDGAR filing entry."""
        published_at = self._parse_date(filing_date)

        accession_nodash = accession.replace("-", "")
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_nodash}/{primary_doc}"

        content: dict[str, Any] = {
            "accession_number": accession,
            "form_type": form_type,
            "filing_date": filing_date,
            "company_name": company_name,
            "cik": cik_padded,
            "tickers": company_tickers,
            "primary_document": primary_doc,
            "primary_doc_description": description,
            "document_url": doc_url,
            "filing_url": f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_nodash}/",
        }

        return RecordCandidate(
            natural_key=f"sec:{accession}",
            published_at=published_at,
            content=content,
            metadata=Metadata(
                source=self._name,
                source_type=f"sec.{form_type.lower().replace('/', '_')}",
                extra={
                    "cik": cik_padded,
                    "company": company_name,
                    "form_type": form_type,
                },
            ),
        )

    async def _fetch_candidates(self) -> AsyncIterator[RecordCandidate]:
        """Yield RecordCandidate for each filing."""

        cik = self._cik
        if not cik and self._ticker:
            cik = await self._resolve_ticker(self._ticker)
            if not cik:
                raise FeedError(
                    f"Could not resolve ticker '{self._ticker}' to CIK",
                    source=self._name,
                )

        # Zero-pad CIK to 10 digits
        cik_padded = cik.lstrip("0").zfill(10)

        url = SUBMISSIONS_API.format(cik=cik_padded)
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }

        from feedspine.core.config import get_settings

        _timeout = get_settings().adapter_timeout

        async with httpx.AsyncClient(timeout=_timeout, headers=headers) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                raise FeedError(
                    f"EDGAR API returned {e.response.status_code} for CIK {cik_padded}",
                    source=self._name,
                    cause=e,
                ) from e

            company_name = data.get("name", "")
            company_tickers = data.get("tickers", [])

            # Recent filings are in data["filings"]["recent"]
            recent = data.get("filings", {}).get("recent", {})
            if not recent:
                return

            accession_numbers = recent.get("accessionNumber", [])
            form_types = recent.get("form", [])
            filing_dates = recent.get("filingDate", [])
            primary_docs = recent.get("primaryDocument", [])
            primary_descriptions = recent.get("primaryDocDescription", [])

            count = 0
            for i in range(len(accession_numbers)):
                if count >= self._max_filings:
                    break

                form_type = form_types[i] if i < len(form_types) else ""
                if self._form_types and form_type.upper() not in self._form_types:
                    continue

                accession = accession_numbers[i]
                filing_date = filing_dates[i] if i < len(filing_dates) else ""
                primary_doc = primary_docs[i] if i < len(primary_docs) else ""
                description = primary_descriptions[i] if i < len(primary_descriptions) else ""

                candidate = self._build_filing_candidate(
                    accession=accession,
                    form_type=form_type,
                    filing_date=filing_date,
                    primary_doc=primary_doc,
                    description=description,
                    company_name=company_name,
                    company_tickers=company_tickers,
                    cik_padded=cik_padded,
                )

                # Optionally fetch full document text
                if self._include_document and primary_doc:
                    await self._rate_limiter.acquire()
                    accession_nodash = accession.replace("-", "")
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_nodash}/{primary_doc}"
                    doc_text = await self._fetch_document(client, doc_url)
                    if doc_text:
                        candidate.content["document_text"] = doc_text[:500_000]
                        candidate.content["document_length"] = len(doc_text)

                yield candidate
                count += 1

    async def _resolve_ticker(self, ticker: str) -> str | None:
        """Resolve a ticker symbol to a CIK via EDGAR company tickers JSON."""
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": self._user_agent}

        from feedspine.core.config import get_settings

        async with httpx.AsyncClient(timeout=get_settings().adapter_timeout, headers=headers) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                return None

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry.get("cik_str", ""))
        return None

    async def _fetch_document(self, client: Any, url: str) -> str | None:
        """Fetch a filing document's text content."""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception:
            logger.debug("Failed to fetch document: %s", url, exc_info=True)
            return None

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse EDGAR date format (YYYY-MM-DD)."""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return datetime.now(UTC)

    # Stubs for abstract methods (not used in generator mode)
    async def _fetch_items(self) -> list[Any]:
        return []  # pragma: no cover

    def _to_candidate(self, item: Any) -> RecordCandidate:
        raise NotImplementedError  # pragma: no cover
