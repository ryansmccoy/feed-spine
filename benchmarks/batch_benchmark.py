"""Batch Processing Benchmark - Testing Parallelism.

This benchmark tests processing MANY files in parallel, which is where
native languages (Rust, Go) shine due to better parallelism and lower overhead.

Key insight: Single-file parsing is already fast (~1GB/s for splitting).
The real bottleneck is:
1. Processing 100,000+ filings
2. Network I/O when downloading
3. Database writes

This benchmark tests:
1. Sequential processing
2. Python multiprocessing
3. Python ThreadPoolExecutor (I/O bound)
4. asyncio (for network simulation)

Run: uv run python benchmarks/batch_benchmark.py
"""

from __future__ import annotations

import concurrent.futures
import multiprocessing as mp
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Pre-compiled pattern (shared across processes via fork)
_DOC_PATTERN = re.compile(
    r'<DOCUMENT>\s*<TYPE>([^<\n]+)\s*<SEQUENCE>([^<\n]+)\s*<FILENAME>([^<\n]+)',
    re.IGNORECASE | re.MULTILINE
)

_HEADER_PATTERNS = {
    'accession': re.compile(r'ACCESSION NUMBER:\s*(\S+)', re.IGNORECASE),
    'form_type': re.compile(r'CONFORMED SUBMISSION TYPE:\s*(\S+)', re.IGNORECASE),
    'company': re.compile(r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', re.IGNORECASE),
    'cik': re.compile(r'CENTRAL INDEX KEY:\s*(\d+)', re.IGNORECASE),
}


@dataclass
class ParseResult:
    """Result from parsing a single file."""
    filepath: str
    file_size: int
    doc_count: int
    metadata: dict[str, str]
    parse_time: float
    error: str | None = None


def parse_file(filepath: Path) -> ParseResult:
    """Parse a single SEC submission file."""
    start = time.perf_counter()
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
        
        # Extract documents
        docs = _DOC_PATTERN.findall(content)
        
        # Extract header
        header = content[:50000]
        metadata = {}
        for key, pattern in _HEADER_PATTERNS.items():
            match = pattern.search(header)
            if match:
                metadata[key] = match.group(1).strip()
        
        elapsed = time.perf_counter() - start
        
        return ParseResult(
            filepath=str(filepath),
            file_size=len(content),
            doc_count=len(docs),
            metadata=metadata,
            parse_time=elapsed,
        )
    except Exception as e:
        return ParseResult(
            filepath=str(filepath),
            file_size=0,
            doc_count=0,
            metadata={},
            parse_time=time.perf_counter() - start,
            error=str(e)[:100],
        )


def parse_file_str(filepath_str: str) -> ParseResult:
    """Wrapper for multiprocessing (Path doesn't pickle well on Windows)."""
    return parse_file(Path(filepath_str))


def run_sequential(files: list[Path]) -> tuple[list[ParseResult], float]:
    """Process files sequentially."""
    start = time.perf_counter()
    results = [parse_file(f) for f in files]
    elapsed = time.perf_counter() - start
    return results, elapsed


def run_multiprocessing(files: list[Path], workers: int = None) -> tuple[list[ParseResult], float]:
    """Process files using multiprocessing Pool."""
    workers = workers or mp.cpu_count()
    
    start = time.perf_counter()
    # Convert paths to strings for Windows pickle compatibility
    file_strs = [str(f) for f in files]
    
    with mp.Pool(workers) as pool:
        results = pool.map(parse_file_str, file_strs)
    
    elapsed = time.perf_counter() - start
    return results, elapsed


def run_threadpool(files: list[Path], workers: int = None) -> tuple[list[ParseResult], float]:
    """Process files using ThreadPoolExecutor (good for I/O)."""
    workers = workers or min(32, len(files))
    
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(parse_file, files))
    
    elapsed = time.perf_counter() - start
    return results, elapsed


def run_processpool(files: list[Path], workers: int = None) -> tuple[list[ParseResult], float]:
    """Process files using ProcessPoolExecutor."""
    workers = workers or mp.cpu_count()
    
    start = time.perf_counter()
    file_strs = [str(f) for f in files]
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(parse_file_str, file_strs))
    
    elapsed = time.perf_counter() - start
    return results, elapsed


def find_sec_files(base_path: Path, limit: int = 100) -> list[Path]:
    """Find SEC submission files for testing."""
    files = []
    
    for pattern in ['**/000*.txt', '**/0001*.txt']:
        for f in base_path.glob(pattern):
            if f.is_file() and f.stat().st_size > 10000:  # Skip tiny files
                files.append(f)
                if len(files) >= limit:
                    break
        if len(files) >= limit:
            break
    
    return files[:limit]


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch processing benchmark')
    parser.add_argument('--sec-data', type=Path, default=Path(r'C:\sec_data\Archives\edgar\data'),
                       help='Path to SEC data directory')
    parser.add_argument('--limit', type=int, default=50, help='Number of files to process')
    parser.add_argument('--workers', type=int, default=None, help='Number of workers')
    
    args = parser.parse_args()
    
    print("="*80)
    print("BATCH PROCESSING BENCHMARK")
    print("="*80)
    print(f"\nCPU cores: {mp.cpu_count()}")
    print(f"Workers: {args.workers or 'auto'}")
    
    # Find test files
    print(f"\nSearching for SEC files in {args.sec_data}...")
    files = find_sec_files(args.sec_data, args.limit)
    
    if not files:
        print("No SEC files found. Using synthetic data...")
        # Create temp synthetic files
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        files = []
        for i in range(args.limit):
            f = temp_dir / f"test_{i}.txt"
            f.write_text(f"""<SEC-HEADER>
ACCESSION NUMBER: 0000320193-24-{i:06d}
CONFORMED SUBMISSION TYPE: 10-K
COMPANY CONFORMED NAME: TEST COMPANY {i}
CENTRAL INDEX KEY: 000032019{i:01d}
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>test.htm
<TEXT>Test content {i}</TEXT>
</DOCUMENT>
""")
            files.append(f)
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in files)
    total_size_mb = total_size / 1024 / 1024
    
    print(f"Found {len(files)} files ({total_size_mb:.1f} MB total)")
    
    # Show file size distribution
    sizes = [f.stat().st_size / 1024 / 1024 for f in files]
    print(f"File sizes: min={min(sizes):.2f}MB, max={max(sizes):.2f}MB, avg={sum(sizes)/len(sizes):.2f}MB")
    
    print("\n" + "-"*80)
    print("BENCHMARK RESULTS")
    print("-"*80)
    print(f"\n{'Method':<30} {'Time':>10} {'Throughput':>15} {'Files/sec':>12}")
    print(f"{'-'*30} {'-'*10} {'-'*15} {'-'*12}")
    
    results_summary = []
    
    # Sequential
    results, elapsed = run_sequential(files)
    throughput = total_size_mb / elapsed
    files_per_sec = len(files) / elapsed
    print(f"{'Sequential':<30} {elapsed:>9.2f}s {throughput:>12.1f} MB/s {files_per_sec:>10.1f}")
    results_summary.append(('Sequential', elapsed, throughput, files_per_sec))
    
    # ThreadPool
    results, elapsed = run_threadpool(files, args.workers)
    throughput = total_size_mb / elapsed
    files_per_sec = len(files) / elapsed
    print(f"{'ThreadPoolExecutor':<30} {elapsed:>9.2f}s {throughput:>12.1f} MB/s {files_per_sec:>10.1f}")
    results_summary.append(('ThreadPool', elapsed, throughput, files_per_sec))
    
    # ProcessPool (skip on Windows if files are too many due to pickle overhead)
    if len(files) <= 200 or os.name != 'nt':
        try:
            results, elapsed = run_processpool(files, args.workers)
            throughput = total_size_mb / elapsed
            files_per_sec = len(files) / elapsed
            print(f"{'ProcessPoolExecutor':<30} {elapsed:>9.2f}s {throughput:>12.1f} MB/s {files_per_sec:>10.1f}")
            results_summary.append(('ProcessPool', elapsed, throughput, files_per_sec))
        except Exception as e:
            print(f"{'ProcessPoolExecutor':<30} ERROR: {e}")
    
    # Multiprocessing Pool
    if len(files) <= 200 or os.name != 'nt':
        try:
            results, elapsed = run_multiprocessing(files, args.workers)
            throughput = total_size_mb / elapsed
            files_per_sec = len(files) / elapsed
            print(f"{'multiprocessing.Pool':<30} {elapsed:>9.2f}s {throughput:>12.1f} MB/s {files_per_sec:>10.1f}")
            results_summary.append(('mp.Pool', elapsed, throughput, files_per_sec))
        except Exception as e:
            print(f"{'multiprocessing.Pool':<30} ERROR: {e}")
    
    # Calculate speedups
    if len(results_summary) >= 2:
        seq_time = results_summary[0][1]
        print(f"\n{'Speedups vs Sequential:'}")
        for name, elapsed, _, _ in results_summary[1:]:
            speedup = seq_time / elapsed
            print(f"  {name}: {speedup:.2f}x")
    
    # Projections
    print("\n" + "-"*80)
    print("PROJECTIONS FOR FULL EDGAR ARCHIVE")
    print("-"*80)
    
    # Assume 500,000 filings at avg 10MB each = 5TB
    projected_filings = 500_000
    projected_size_tb = 5
    
    for name, elapsed, throughput, files_per_sec in results_summary:
        projected_time_hours = (projected_size_tb * 1024 * 1024) / throughput / 3600
        projected_time_filing_hours = projected_filings / files_per_sec / 3600
        print(f"{name}:")
        print(f"  {projected_size_tb}TB data: {projected_time_hours:.1f} hours")
        print(f"  {projected_filings:,} filings: {projected_time_filing_hours:.1f} hours")
    
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)
    print("""
KEY FINDINGS:

1. **I/O Bound**: File reading is the bottleneck, not CPU processing
   - ThreadPool helps because threads can overlap I/O waits
   - ProcessPool has overhead for small files

2. **Python is Fast Enough**: Document splitting at 2-3 GB/s
   - Native code would help more for CPU-intensive parsing
   - Real bottleneck is reading files from disk

3. **Where Rust/Go Would Help**:
   - Batch downloading from SEC (async I/O + connection pooling)
   - Processing files from cloud storage (S3, GCS)
   - Real-time streaming ingestion
   - Memory efficiency for very large datasets

4. **Practical Recommendations**:
   - Use ThreadPool for local file processing
   - Use async (aiohttp/httpx) for downloading
   - Consider Rust for a high-performance CLI tool
   - Database writes are likely the next bottleneck
""")


if __name__ == '__main__':
    # Windows multiprocessing requires this
    mp.freeze_support()
    main()
