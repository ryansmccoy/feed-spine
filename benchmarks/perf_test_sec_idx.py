"""Performance benchmarks for SEC IDX file parsing and storage.

Tests FeedSpine's ability to handle large SEC EDGAR index files.
Uses real SEC master.idx files from B:\sec_gov\Archives\edgar\full-index

IDENTIFIED BOTTLENECKS (from code analysis):
1. JSON Serialization - json.dumps() called for every content field on store
2. Pydantic model_dump_json() - Called for metadata on every store operation  
3. Sequential dedup lookups - Pipeline.process() does get_by_natural_key() per record
4. No parallel parsing - FileFeedAdapter processes rows sequentially
5. Memory accumulation - Large files load all candidates before processing
6. String operations - Repeated datetime.isoformat() calls in store_batch

Run with: python -m pytest benchmarks/perf_test_sec_idx.py -v -s
Or standalone: python benchmarks/perf_test_sec_idx.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# FeedSpine imports
from feedspine.adapter.file import FileFeedAdapter, FileSnapshot
from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate
from feedspine.storage.duckdb import DuckDBStorage
from feedspine.storage.memory import MemoryStorage


# ============================================================================
# SEC IDX File Adapter
# ============================================================================

class SECIndexAdapter(FileFeedAdapter):
    """Adapter for SEC EDGAR master.idx files.
    
    Format:
    - Header: 11 lines of metadata
    - Separator: Dashed line
    - Data: Pipe-delimited rows
    - Fields: CIK|Company Name|Form Type|Date Filed|Filename
    """
    
    def __init__(self, idx_path: str | Path, name: str = "sec-master-idx") -> None:
        super().__init__(name=name, source_url=str(idx_path))
        self.idx_path = Path(idx_path)
        self._content_cache: bytes | None = None
    
    async def _fetch_file(self) -> bytes:
        """Read IDX file from disk."""
        if self._content_cache is None:
            self._content_cache = self.idx_path.read_bytes()
        return self._content_cache
    
    async def _parse_file(self, content: bytes) -> AsyncIterator[dict[str, Any]]:
        """Parse SEC master.idx format (pipe-delimited with header)."""
        lines = content.decode("utf-8", errors="replace").splitlines()
        
        # Skip header (11 lines) and separator line
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith("---"):
                data_start = i + 1
                break
        
        for line in lines[data_start:]:
            if not line.strip():
                continue
            
            parts = line.split("|")
            if len(parts) >= 5:
                yield {
                    "cik": parts[0].strip(),
                    "company_name": parts[1].strip(),
                    "form_type": parts[2].strip(),
                    "date_filed": parts[3].strip(),
                    "filename": parts[4].strip(),
                }
    
    def _row_to_candidate(self, row: dict[str, Any], index: int) -> RecordCandidate:
        """Convert IDX row to RecordCandidate."""
        # Natural key: CIK + filename (unique filing identifier)
        natural_key = f"sec:{row['cik']}:{row['filename']}"
        
        # Parse date
        try:
            pub_date = datetime.strptime(row["date_filed"], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pub_date = datetime.now(UTC)
        
        return RecordCandidate(
            natural_key=natural_key,
            content={
                "cik": row["cik"],
                "company_name": row["company_name"],
                "form_type": row["form_type"],
                "date_filed": row["date_filed"],
                "filename": row["filename"],
                "sec_url": f"https://www.sec.gov/Archives/{row['filename']}",
            },
            metadata=Metadata(source="sec-edgar-idx"),
            published_at=pub_date,
        )


# ============================================================================
# Benchmark Utilities  
# ============================================================================

class BenchmarkTimer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time: float = 0
        self.end_time: float = 0
        self.elapsed: float = 0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time


class BenchmarkResult:
    """Stores benchmark results with statistics."""
    
    def __init__(self, name: str, iterations: list[float], record_count: int):
        self.name = name
        self.iterations = iterations
        self.record_count = record_count
        self.total_time = sum(iterations)
        self.mean_time = statistics.mean(iterations) if iterations else 0
        self.std_dev = statistics.stdev(iterations) if len(iterations) > 1 else 0
        self.min_time = min(iterations) if iterations else 0
        self.max_time = max(iterations) if iterations else 0
        self.records_per_sec = record_count / self.mean_time if self.mean_time > 0 else 0
    
    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Records: {self.record_count:,}\n"
            f"  Mean: {self.mean_time:.4f}s (±{self.std_dev:.4f}s)\n"
            f"  Range: [{self.min_time:.4f}s - {self.max_time:.4f}s]\n"
            f"  Throughput: {self.records_per_sec:,.0f} records/sec"
        )


# ============================================================================
# Benchmark Tests
# ============================================================================

async def benchmark_idx_parsing(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: Raw IDX file parsing speed.
    
    Tests the _parse_file method to measure pure parsing performance
    without any storage overhead.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    times = []
    record_count = 0
    
    for _ in range(iterations):
        with BenchmarkTimer("parse") as timer:
            count = 0
            async for _ in adapter._parse_file(content):
                count += 1
        times.append(timer.elapsed)
        record_count = count
    
    return BenchmarkResult("IDX Parsing (raw)", times, record_count)


async def benchmark_candidate_creation(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: RecordCandidate creation from parsed rows.
    
    Tests parsing + Pydantic model instantiation.
    This is where type validation overhead appears.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    times = []
    record_count = 0
    
    for _ in range(iterations):
        with BenchmarkTimer("candidate_creation") as timer:
            count = 0
            async for row in adapter._parse_file(content):
                candidate = adapter._row_to_candidate(row, count)
                count += 1
        times.append(timer.elapsed)
        record_count = count
    
    return BenchmarkResult("Candidate Creation", times, record_count)


async def benchmark_record_creation(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: Full Record creation from candidates.
    
    Tests the full pipeline of parsing -> candidate -> Record model.
    Record creation includes UUID generation and timestamp assignment.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    times = []
    record_count = 0
    
    for _ in range(iterations):
        with BenchmarkTimer("record_creation") as timer:
            count = 0
            async for row in adapter._parse_file(content):
                candidate = adapter._row_to_candidate(row, count)
                record = Record.from_candidate(candidate, layer=Layer.BRONZE)
                count += 1
        times.append(timer.elapsed)
        record_count = count
    
    return BenchmarkResult("Record Creation", times, record_count)


async def benchmark_json_serialization(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: JSON serialization overhead.
    
    BOTTLENECK IDENTIFIED: store() calls json.dumps() for content
    and model_dump_json() for metadata on EVERY record.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    times = []
    
    for _ in range(iterations):
        with BenchmarkTimer("json_serialization") as timer:
            for record in records:
                # This is what store() does internally
                _ = json.dumps(record.content)
                _ = record.metadata.model_dump_json()
        times.append(timer.elapsed)
    
    return BenchmarkResult("JSON Serialization", times, len(records))


async def benchmark_memory_storage(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: MemoryStorage write performance.
    
    Tests storage overhead without database I/O.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    times = []
    
    for _ in range(iterations):
        storage = MemoryStorage()
        await storage.initialize()
        
        with BenchmarkTimer("memory_storage") as timer:
            for record in records:
                await storage.store(record)
        
        times.append(timer.elapsed)
        await storage.close()
    
    return BenchmarkResult("Memory Storage (single)", times, len(records))


async def benchmark_memory_storage_batch(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: MemoryStorage batch write performance.
    
    Compares batch vs single-record writes.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    times = []
    
    for _ in range(iterations):
        storage = MemoryStorage()
        await storage.initialize()
        
        with BenchmarkTimer("memory_storage_batch") as timer:
            await storage.store_batch(records, batch_size=5000)
        
        times.append(timer.elapsed)
        await storage.close()
    
    return BenchmarkResult("Memory Storage (batch)", times, len(records))


async def benchmark_duckdb_storage(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: DuckDB single-record storage.
    
    Tests DuckDB write performance with INSERT OR REPLACE.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    times = []
    
    for _ in range(iterations):
        storage = DuckDBStorage(":memory:")
        await storage.initialize()
        
        with BenchmarkTimer("duckdb_storage") as timer:
            for record in records:
                await storage.store(record)
        
        times.append(timer.elapsed)
        await storage.close()
    
    return BenchmarkResult("DuckDB Storage (single)", times, len(records))


async def benchmark_duckdb_storage_batch(
    idx_path: Path, 
    iterations: int = 3,
    batch_sizes: list[int] | None = None,
) -> list[BenchmarkResult]:
    """Benchmark: DuckDB batch storage with different batch sizes.
    
    Tests how batch_size affects write throughput.
    """
    if batch_sizes is None:
        batch_sizes = [100, 500, 1000, 5000, 10000]
    
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    results = []
    
    for batch_size in batch_sizes:
        times = []
        
        for _ in range(iterations):
            storage = DuckDBStorage(":memory:")
            await storage.initialize()
            
            with BenchmarkTimer(f"duckdb_batch_{batch_size}") as timer:
                await storage.store_batch(records, batch_size=batch_size)
            
            times.append(timer.elapsed)
            await storage.close()
        
        results.append(BenchmarkResult(
            f"DuckDB Batch (size={batch_size})",
            times,
            len(records),
        ))
    
    return results


async def benchmark_dedup_lookup(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: Deduplication lookup overhead.
    
    BOTTLENECK IDENTIFIED: Pipeline.process() calls get_by_natural_key()
    for EVERY record to check for duplicates.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records and store them
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    # Store all records first
    storage = DuckDBStorage(":memory:")
    await storage.initialize()
    await storage.store_batch(records, batch_size=5000)
    
    times = []
    
    for _ in range(iterations):
        with BenchmarkTimer("dedup_lookup") as timer:
            for record in records:
                await storage.get_by_natural_key(record.natural_key)
        times.append(timer.elapsed)
    
    await storage.close()
    
    return BenchmarkResult("Dedup Lookup (per record)", times, len(records))


async def benchmark_dedup_exists(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: exists_by_natural_key() vs get_by_natural_key().
    
    Tests if checking existence only is faster than full record retrieval.
    """
    adapter = SECIndexAdapter(idx_path)
    content = await adapter._fetch_file()
    
    # Pre-create records and store them
    records = []
    async for row in adapter._parse_file(content):
        candidate = adapter._row_to_candidate(row, len(records))
        records.append(Record.from_candidate(candidate, layer=Layer.BRONZE))
    
    # Store all records first
    storage = DuckDBStorage(":memory:")
    await storage.initialize()
    await storage.store_batch(records, batch_size=5000)
    
    times = []
    
    for _ in range(iterations):
        with BenchmarkTimer("dedup_exists") as timer:
            for record in records:
                await storage.exists_by_natural_key(record.natural_key)
        times.append(timer.elapsed)
    
    await storage.close()
    
    return BenchmarkResult("Exists Check (per record)", times, len(records))


async def benchmark_full_pipeline(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: Complete pipeline from file to storage.
    
    Tests the full end-to-end flow:
    1. File read
    2. Parse
    3. Candidate creation
    4. Record creation
    5. Storage
    """
    times = []
    record_count = 0
    
    for _ in range(iterations):
        adapter = SECIndexAdapter(idx_path)
        storage = DuckDBStorage(":memory:")
        await storage.initialize()
        
        with BenchmarkTimer("full_pipeline") as timer:
            count = 0
            async for candidate in adapter.fetch():
                record = Record.from_candidate(candidate, layer=Layer.BRONZE)
                await storage.store(record)
                count += 1
        
        times.append(timer.elapsed)
        record_count = count
        await storage.close()
    
    return BenchmarkResult("Full Pipeline (single store)", times, record_count)


async def benchmark_full_pipeline_batched(idx_path: Path, iterations: int = 3) -> BenchmarkResult:
    """Benchmark: Pipeline with batched storage.
    
    Collects records in memory then batch stores.
    Tests memory vs I/O tradeoff.
    """
    times = []
    record_count = 0
    
    for _ in range(iterations):
        adapter = SECIndexAdapter(idx_path)
        storage = DuckDBStorage(":memory:")
        await storage.initialize()
        
        with BenchmarkTimer("full_pipeline_batched") as timer:
            records = []
            async for candidate in adapter.fetch():
                record = Record.from_candidate(candidate, layer=Layer.BRONZE)
                records.append(record)
            
            await storage.store_batch(records, batch_size=5000)
        
        times.append(timer.elapsed)
        record_count = len(records)
        await storage.close()
    
    return BenchmarkResult("Full Pipeline (batched)", times, record_count)


# ============================================================================
# Main Runner
# ============================================================================

async def run_benchmarks(idx_path: Path, quick: bool = False):
    """Run all benchmarks and print results."""
    iterations = 1 if quick else 3
    
    print("=" * 70)
    print("FeedSpine SEC IDX Performance Benchmarks")
    print("=" * 70)
    print(f"Test file: {idx_path}")
    print(f"File size: {idx_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Iterations: {iterations}")
    print("=" * 70)
    print()
    
    results = []
    
    # Parsing benchmarks
    print("Running: IDX Parsing...")
    results.append(await benchmark_idx_parsing(idx_path, iterations))
    
    print("Running: Candidate Creation...")
    results.append(await benchmark_candidate_creation(idx_path, iterations))
    
    print("Running: Record Creation...")
    results.append(await benchmark_record_creation(idx_path, iterations))
    
    print("Running: JSON Serialization...")
    results.append(await benchmark_json_serialization(idx_path, iterations))
    
    # Storage benchmarks
    print("Running: Memory Storage (single)...")
    results.append(await benchmark_memory_storage(idx_path, iterations))
    
    print("Running: Memory Storage (batch)...")
    results.append(await benchmark_memory_storage_batch(idx_path, iterations))
    
    print("Running: DuckDB Storage (single)...")
    results.append(await benchmark_duckdb_storage(idx_path, iterations))
    
    print("Running: DuckDB Batch Storage (various sizes)...")
    batch_results = await benchmark_duckdb_storage_batch(idx_path, iterations)
    results.extend(batch_results)
    
    # Dedup benchmarks
    print("Running: Dedup Lookup...")
    results.append(await benchmark_dedup_lookup(idx_path, iterations))
    
    print("Running: Exists Check...")
    results.append(await benchmark_dedup_exists(idx_path, iterations))
    
    # Full pipeline
    print("Running: Full Pipeline (single)...")
    results.append(await benchmark_full_pipeline(idx_path, iterations))
    
    print("Running: Full Pipeline (batched)...")
    results.append(await benchmark_full_pipeline_batched(idx_path, iterations))
    
    # Print results
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    for result in results:
        print()
        print(result)
    
    # Print bottleneck analysis
    print()
    print("=" * 70)
    print("BOTTLENECK ANALYSIS")
    print("=" * 70)
    
    # Find slowest operations
    sorted_results = sorted(results, key=lambda r: 1/r.records_per_sec if r.records_per_sec > 0 else float('inf'))
    
    print("\nSlowest operations (records/sec):")
    for i, result in enumerate(sorted_results[:5], 1):
        print(f"  {i}. {result.name}: {result.records_per_sec:,.0f} rec/s")
    
    print("\nFastest operations (records/sec):")
    for i, result in enumerate(sorted_results[-5:], 1):
        print(f"  {i}. {result.name}: {result.records_per_sec:,.0f} rec/s")
    
    return results


async def run_multi_file_benchmark(idx_dir: Path, max_files: int = 10):
    """Benchmark across multiple IDX files.
    
    Tests scaling behavior with multiple quarters of data.
    """
    idx_files = sorted(idx_dir.glob("**/master.idx"))[:max_files]
    
    print("=" * 70)
    print("Multi-File Scaling Benchmark")
    print("=" * 70)
    print(f"Files: {len(idx_files)}")
    print()
    
    total_records = 0
    total_time = 0
    
    storage = DuckDBStorage(":memory:")
    await storage.initialize()
    
    for idx_path in idx_files:
        adapter = SECIndexAdapter(idx_path)
        
        with BenchmarkTimer("file") as timer:
            records = []
            async for candidate in adapter.fetch():
                record = Record.from_candidate(candidate, layer=Layer.BRONZE)
                records.append(record)
            
            await storage.store_batch(records, batch_size=5000, on_conflict="skip")
        
        total_records += len(records)
        total_time += timer.elapsed
        
        print(f"  {idx_path.parent.parent.name}/{idx_path.parent.name}: "
              f"{len(records):,} records in {timer.elapsed:.2f}s "
              f"({len(records)/timer.elapsed:,.0f} rec/s)")
    
    await storage.close()
    
    print()
    print(f"Total: {total_records:,} records in {total_time:.2f}s")
    print(f"Average: {total_records/total_time:,.0f} records/sec")


def find_idx_file(base_path: str = r"B:\sec_gov") -> Path:
    """Find a suitable IDX file for testing."""
    base = Path(base_path)
    
    # Try to find a recent file (2024 Q1 is a good size)
    candidates = [
        base / "Archives/edgar/full-index/2024/QTR1/master.idx",
        base / "Archives/edgar/full-index/2023/QTR4/master.idx",
        base / "Archives/edgar/full-index/2023/QTR1/master.idx",
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    # Find any idx file
    idx_files = list((base / "Archives/edgar/full-index").glob("**/master.idx"))
    if idx_files:
        return max(idx_files, key=lambda p: p.stat().st_size)
    
    raise FileNotFoundError(f"No master.idx files found in {base}")


if __name__ == "__main__":
    import sys
    
    # Find test file
    try:
        idx_path = find_idx_file()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure SEC data is available at B:\\sec_gov")
        sys.exit(1)
    
    # Run benchmarks
    quick = "--quick" in sys.argv
    multi = "--multi" in sys.argv
    
    if multi:
        asyncio.run(run_multi_file_benchmark(
            Path(r"B:\sec_gov\Archives\edgar\full-index"),
            max_files=20,
        ))
    else:
        asyncio.run(run_benchmarks(idx_path, quick=quick))
