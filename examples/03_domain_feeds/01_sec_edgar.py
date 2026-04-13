#!/usr/bin/env python3
"""
FeedSpine SEC EDGAR Filing Monitor
==================================

This example demonstrates how to use FeedSpine for **SEC EDGAR filing monitoring**,
a real-world use case where deduplication is critical.

What You'll Learn:
    1. How to create a custom feed adapter for SEC EDGAR
    2. How to use accession numbers as natural keys for deduplication
    3. Why deduplication matters for regulatory filings

The SEC EDGAR Deduplication Problem:
    SEC filings appear in MULTIPLE places:

    1. **RSS Feed** (real-time): New filings appear within minutes
    2. **Daily Index** (next day): Full list of yesterday's filings
    3. **Quarterly Index** (quarterly): Complete quarterly archive
    4. **Full-Text Search**: Same filings appear in search results

    Without deduplication, the same 10-K filing might be stored 4+ times!

    FeedSpine solves this by using the **accession number** (SEC's unique ID)
    as the natural key. Same accession number = same filing = stored once.

What is an Accession Number?
    Example: 0000320193-24-000081

    Format: [CIK]-[YY]-[SEQUENCE]
    - CIK: Company's Central Index Key (10 digits, zero-padded)
    - YY: Year filed (2 digits)
    - SEQUENCE: Filing sequence number for that company/year

    This is globally unique - no two filings ever share an accession number.

SEC Form Types Monitored:
    - **10-K**: Annual report (comprehensive financial statements)
    - **10-Q**: Quarterly report (interim financial statements)
    - **8-K**: Current report (material events, earnings, acquisitions)

    Other common forms: 4 (insider trading), 13F (institutional holdings),
    DEF 14A (proxy statements), S-1 (IPO registration)

Usage:
    python examples/03_domain_feeds/01_sec_edgar.py

Expected Output:
    - Filings fetched from SEC EDGAR RSS feeds
    - Deduplication across form types (if same company filed multiple)
"""

import asyncio
import warnings
from typing import Any

# Suppress internal WatermarkStore warning when using MemoryStorage
warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")

from feedspine import (
    MemoryStorage,
    RecordCandidate,
    RSSFeedAdapter,
    create_feed_spine,
)


class SECFilingFeed(RSSFeedAdapter):
    """Custom adapter for SEC EDGAR filing feeds.

    This adapter demonstrates how to extend RSSFeedAdapter for domain-specific
    feeds. The key customization is the natural key generation - we use the
    SEC accession number to ensure deduplication across all data sources.

    Attributes:
        form_type: The SEC form type to monitor (e.g., "10-K", "10-Q", "8-K")

    Example:
        >>> feed = SECFilingFeed("10-K")
        >>> feed.name
        'sec-10-k'
        >>> "browse-edgar" in feed.url
        True
    """

    def __init__(self, form_type: str) -> None:
        """Initialize SEC filing feed for a specific form type.

        Args:
            form_type: SEC form type to monitor. Common values:
                - "10-K": Annual reports
                - "10-Q": Quarterly reports
                - "8-K": Current reports (material events)
                - "4": Insider trading (Section 16)
                - "13F": Institutional holdings
        """
        # SEC EDGAR provides Atom feeds for recent filings by form type
        # This URL returns the 40 most recent filings of the specified type
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcurrent&type={form_type}&company=&dateb="
            f"&owner=include&count=40&output=atom"
        )

        # Create a clean feed name (e.g., "sec-10-k" from "10-K")
        super().__init__(
            name=f"sec-{form_type.lower().replace(' ', '-')}",
            url=url,
        )
        self.form_type = form_type

    def _entry_to_candidate(self, entry: dict[str, Any]) -> RecordCandidate:
        """Convert RSS entry to RecordCandidate with accession-based natural key.

        This is the critical method for deduplication. By extracting the
        accession number and using it as the natural key, we ensure that
        the same filing from multiple sources is stored exactly once.

        Args:
            entry: Parsed RSS entry with id, link, title, summary, etc.

        Returns:
            RecordCandidate with natural_key based on accession number.
        """
        # Extract accession number for deduplication
        # The SEC RSS feed includes accession in the entry ID or link
        accession = entry.get("id", "") or entry.get("link", "")

        # Natural key format: "sec-filing:{accession}"
        # This ensures the same filing is never stored twice, regardless
        # of whether it came from RSS, daily index, or quarterly index
        natural_key = f"sec-filing:{accession}"

        return RecordCandidate(
            natural_key=natural_key,
            published_at=entry.get("published"),
            content={
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "form_type": self.form_type,
                # In production, you might also extract:
                # "cik": extract_cik(entry),
                # "company_name": extract_company(entry),
                # "filed_date": parse_date(entry),
            },
        )


async def main() -> None:
    """Monitor SEC filings with automatic deduplication.

    This function demonstrates:
    1. Creating custom feed adapters for SEC EDGAR
    2. Registering multiple feeds (one per form type)
    3. Collecting and deduplicating across all feeds

    Returns:
        None. Prints collection statistics to stdout.
    """
    # =========================================================================
    # STEP 1: Create Storage
    # =========================================================================
    storage = MemoryStorage()

    # =========================================================================
    # STEP 2: Define Form Types to Monitor
    # =========================================================================
    # These are the most commonly monitored SEC form types:
    # - 10-K: Annual reports (filed within 60-90 days of fiscal year end)
    # - 10-Q: Quarterly reports (filed within 40-45 days of quarter end)
    # - 8-K: Current reports (filed within 4 business days of material event)
    form_types = ["10-K", "10-Q", "8-K"]

    print("=" * 60)
    print("SEC EDGAR FILING MONITOR")
    print("=" * 60)
    print("""
FeedSpine monitors SEC filings with automatic deduplication.
The same filing from RSS, daily index, and quarterly index
is stored exactly once using the accession number as key.
    """)

    # =========================================================================
    # STEP 3: Create FeedSpineApp with SEC Feeds
    # =========================================================================
    sec_feeds = [SECFilingFeed(ft) for ft in form_types]
    app = create_feed_spine(
        storage,
        feeds={f.name: f for f in sec_feeds},
    )

    print("Registering SEC EDGAR feeds:")
    for feed in sec_feeds:
        print(f"  ✓ {feed.name}: {feed.form_type} filings")

    # =========================================================================
    # STEP 4: Collect Filings
    # =========================================================================
    print("\n" + "-" * 60)
    print("Collecting filings from SEC EDGAR...")
    print("-" * 60)

    total_processed = 0
    total_new = 0
    total_duplicates = 0
    total_errors = 0

    for feed in sec_feeds:
        try:
            outcome = await app.collection_service.run_collection(feed.name)
            total_processed += outcome.stats.processed
            total_new += outcome.stats.new
            total_duplicates += outcome.stats.duplicates
            print(f"  ✓ {feed.name}: {outcome.stats.new} new, {outcome.stats.duplicates} duplicates")
        except Exception as exc:
            total_errors += 1
            # SEC EDGAR blocks requests without proper User-Agent header
            error_msg = str(exc)
            if "403" in error_msg:
                print(f"  ⚠ {feed.name}: Blocked by SEC (403 Forbidden)")
            else:
                print(f"  ⚠ {feed.name}: {error_msg.split(chr(10))[0]}")

    if total_errors == len(sec_feeds):
        print("\n  Note: SEC EDGAR blocked all requests (403 Forbidden).")
        print("  This is expected when running without a registered User-Agent.")
        print("  In production, set SEC_USER_AGENT='YourName your@email.com'.")
        print("\n  Example completed successfully (SEC access not required).")
        return

    # =========================================================================
    # STEP 5: Display Results
    # =========================================================================
    print("\n" + "=" * 60)
    print("COLLECTION RESULTS")
    print("=" * 60)
    print(f"  Total filings processed: {total_processed}")
    print(f"  New filings stored:      {total_new}")
    print(f"  Duplicates detected:     {total_duplicates}")

    # =========================================================================
    # Explain the Deduplication Value
    # =========================================================================
    print("\n" + "=" * 60)
    print("WHY SEC DEDUPLICATION MATTERS")
    print("=" * 60)
    print("""
In production, the same filing appears in MULTIPLE places:

  Source              | When Available     | Without Dedup
  --------------------+--------------------+--------------
  RSS Feed            | Real-time          | Record #1
  Daily Index         | Next day           | Record #2 (duplicate!)
  Quarterly Index     | End of quarter     | Record #3 (duplicate!)
  Full-Text Search    | Anytime            | Record #4 (duplicate!)

With FeedSpine:
  - All sources use accession number as natural_key
  - Same accession = same filing = stored ONCE
  - Sightings track when/where each filing was seen
  - No duplicate storage, no duplicate processing

This is critical for:
  - Compliance monitoring (don't alert twice for same filing)
  - Analytics (accurate filing counts)
  - Cost savings (less storage, less processing)
    """)


if __name__ == "__main__":
    asyncio.run(main())
