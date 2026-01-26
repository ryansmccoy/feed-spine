# SEC EDGAR Domain Overview

The SEC EDGAR domain is the **reference implementation** for FeedSpine, demonstrating how to build a complete feed capture system for regulatory filings.

---

## Feed Types

SEC EDGAR provides **4 distinct feed sources** that all contain filing information:

| Feed | URL Pattern | Update Frequency | Use Case |
|------|-------------|------------------|----------|
| **RSS** | `/cgi-bin/browse-edgar?...output=atom` | Real-time (~5 min) | Live monitoring |
| **Daily Index** | `/Archives/edgar/daily-index/.../crawler.YYYYMMDD.idx` | Daily | Daily catch-up |
| **Full Index** | `/Archives/edgar/full-index/YYYY/QTRn/master.idx` | Quarterly | Historical backfill |
| **Monthly XBRL** | `/Archives/edgar/monthly/xbrlrss-YYYY-MM.xml` | Monthly | XBRL-specific filings |

All four feeds produce the **same filing data** - they just have different latencies and formats.

---

## The Natural Key: Accession Number

The **accession number** is the globally unique identifier for every SEC filing:

```
0000320193-24-000081
└────┬────┘ └┬┘ └──┬─┘
     │      │     │
     │      │     └── Sequence number within year
     │      └──────── Year (24 = 2024)
     └─────────────── Filer's CIK (padded)
```

**This is the deduplication key** - the same filing appearing in all 4 feeds has the same accession number.

```python
class SECFilingNormalizer:
    domain = "sec"
    
    def compute_dedup_key(self, candidate: RecordCandidate) -> str:
        # Accession number is globally unique across all SEC filings
        return candidate.metadata["accession_number"]
```

---

## Feed Adapters

### RSS Feed Adapter

Real-time feed that updates every ~5 minutes:

```python
class SECRSSFeed(FeedAdapter):
    """SEC EDGAR real-time RSS feed."""
    
    name = "sec.rss"
    
    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries:
                yield RecordCandidate(
                    natural_key=entry.edgar_accessionnumber,
                    published_at=parse_datetime(entry.edgar_filingdate),
                    content={
                        "form_type": entry.edgar_formtype,
                        "company_name": entry.edgar_companyname,
                        "cik": entry.edgar_ciknumber,
                    },
                    metadata=Metadata(source="sec.rss"),
                )
```

### Daily Index Adapter

Pipe-delimited index files published daily:

```
CIK|Company Name|Form Type|Date Filed|Filename
1000045|NICHOLAS FINANCIAL INC|10-K|2024-06-28|edgar/data/1000045/0001193125-24-123456.txt
```

```python
class SECDailyIndexFeed(FeedAdapter):
    """SEC EDGAR daily crawler.idx files."""
    
    name = "sec.daily_index"
    
    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        # Get dates to fetch based on checkpoint
        for date in self._get_dates_to_fetch():
            url = self._build_url(date)
            content = await self._fetch_url(url)
            
            for line in content.split('\n'):
                if '|' in line:
                    cik, company, form, date_filed, filename = line.split('|')
                    accession = self._extract_accession(filename)
                    
                    yield RecordCandidate(
                        natural_key=accession,
                        published_at=parse_date(date_filed),
                        content={
                            "form_type": form.strip(),
                            "company_name": company.strip(),
                            "cik": cik.strip(),
                        },
                        metadata=Metadata(source="sec.daily_index"),
                    )
```

### Full Index Adapter

Quarterly master.idx files for historical backfill:

```python
class SECFullIndexFeed(FeedAdapter):
    """SEC EDGAR quarterly master.idx files."""
    
    name = "sec.full_index"
    
    def __init__(self, years_back: int = 5):
        self.years_back = years_back
    
    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        for year, quarter in self._get_quarters_to_fetch():
            url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
            # ... parse same pipe-delimited format
```

---

## Deduplication in Action

When the same filing appears in multiple feeds:

```
sec.rss:         0000320193-24-000081  ←─┐
sec.daily_index: 0000320193-24-000081  ←─┼── Same accession = Same record
sec.full_index:  0000320193-24-000081  ←─┘

┌─────────────────────────────────────────────────────────┐
│                    records table                         │
├─────────────────────────────────────────────────────────┤
│ id: uuid-123                                            │
│ natural_key: 0000320193-24-000081                       │
│ layer: BRONZE                                           │
│ published_at: 2024-06-28                                │
│ captured_at: 2024-06-28T10:05:00Z  ← First seen via RSS │
│ seen_count: 3                                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   sightings table                        │
├─────────────────────────────────────────────────────────┤
│ natural_key: 0000320193-24-000081                       │
│ source: sec.rss         │ seen_at: 2024-06-28T10:05Z   │
│ source: sec.daily_index │ seen_at: 2024-06-29T00:15Z   │
│ source: sec.full_index  │ seen_at: 2024-07-01T00:30Z   │
└─────────────────────────────────────────────────────────┘
```

---

## Form Types

Common SEC form types:

| Form | Description | Key Content |
|------|-------------|-------------|
| **10-K** | Annual report | Full financial statements, MD&A, risk factors |
| **10-Q** | Quarterly report | Interim financials, MD&A updates |
| **8-K** | Current report | Material events (earnings, M&A, resignations) |
| **4** | Insider trading | Ownership changes by insiders |
| **13F** | Institutional holdings | Quarterly holdings by institutions |
| **DEF 14A** | Proxy statement | Executive compensation, board info |
| **S-1** | IPO registration | Pre-IPO disclosure |

---

## URL Structure

SEC EDGAR URLs follow a predictable pattern:

```
https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION_NO_DASHES}/

Example for Apple 10-K:
https://www.sec.gov/Archives/edgar/data/320193/000032019324000081/

├── Index page:    {accession}-index.htm
├── Full submission: {accession}.txt
├── Primary document: aapl-20240928.htm
└── Exhibits:      ex21-1.htm, ex31-1.htm, ...
```

---

## Rate Limiting

SEC EDGAR allows **10 requests per second**. We use 8 for safety:

```python
class SECRateLimiter:
    def __init__(self, requests_per_second: float = 8.0):
        self.rate = requests_per_second
        self.bucket = TokenBucket(rate=requests_per_second)
    
    async def acquire(self):
        await self.bucket.acquire()
```

Required headers:
```python
headers = {
    "User-Agent": "Company Name admin@company.com",
    "Accept-Encoding": "gzip, deflate",
}
```

---

## Enrichment Ideas

SEC filings can be enriched with:

| Enrichment | Source | Layer |
|------------|--------|-------|
| Form type normalization | Parsed from filing | SILVER |
| CIK → Ticker mapping | SEC company search | SILVER |
| Filing section extraction | Full text parsing | SILVER |
| Entity extraction (NLP) | spaCy/LLM | GOLD |
| Sentiment analysis | LLM | GOLD |
| Filing summary | LLM | GOLD |
