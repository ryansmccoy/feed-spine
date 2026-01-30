# Performance Tests

This directory contains performance and benchmark tests for FeedSpine.

## Running Performance Tests

```bash
# Run all performance tests (may take several minutes)
pytest tests/performance/ -v

# Skip slow tests in CI
pytest tests/performance/ -m "not slow"

# Run with timing output
pytest tests/performance/ -v --durations=0
```

## Test Scenarios

### Bulk Insert Performance
- 10K records: < 2 seconds (Memory), < 5 seconds (DuckDB)
- 50K records: < 10 seconds (Memory)
- 100K records: < 60 seconds (DuckDB) - SEC quarterly index scale

### Deduplication Performance
- 90% dedup rate (RSS polling scenario)
- 80% dedup rate (daily vs quarterly overlap)
- Sighting updates at scale

### Query Performance
- Layer filtering on large datasets
- Pagination queries
- SQL analytics (DuckDB only)

### Concurrent Operations
- Parallel batch writes
- Mixed read/write workloads

## SEC Feed Context

These tests simulate real SEC feed scenarios:

| Feed Type | Records/Fetch | Typical Overlap |
|-----------|---------------|-----------------|
| Quarterly | ~100,000 | ~20% with prior quarter |
| Daily | ~4,000 | ~80% with quarterly |
| RSS | ~100 | ~90% with daily |

The unified feed deduplicates across all sources, typically filtering
60-90% of records as duplicates.
