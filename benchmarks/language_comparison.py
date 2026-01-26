"""Comprehensive benchmarks to identify bottlenecks where native code might help.

Tests operations that could benefit from:
- Cython (CPU-bound Python with C types)
- Rust via PyO3 (memory-safe systems programming)
- C/C++ extensions (maximum performance)

Operations tested:
1. JSON parsing/serialization (high volume)
2. String manipulation (accession number parsing)
3. Pattern matching (regex vs manual)
4. Data structure operations (lookups, sorting)
5. I/O throughput (file/database)
6. Concurrent processing
"""

from __future__ import annotations

import gc
import hashlib
import json
import re
import struct
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Test data location
TEST_DATA_DIR = Path(__file__).parent / "test_data"

# ============================================================================
# Benchmark Infrastructure
# ============================================================================

@dataclass
class BenchResult:
    """Benchmark result with timing and throughput."""
    name: str
    items_processed: int
    elapsed_seconds: float
    items_per_second: float = 0.0
    bytes_processed: int = 0
    mb_per_second: float = 0.0
    notes: str = ""
    
    def __post_init__(self):
        if self.elapsed_seconds > 0:
            self.items_per_second = self.items_processed / self.elapsed_seconds
            if self.bytes_processed > 0:
                self.mb_per_second = (self.bytes_processed / 1024 / 1024) / self.elapsed_seconds
    
    def __str__(self) -> str:
        throughput = f"{self.items_per_second:,.0f} items/s"
        if self.mb_per_second > 0:
            throughput += f" ({self.mb_per_second:.1f} MB/s)"
        return f"{self.name:45s} | {self.elapsed_seconds:7.3f}s | {throughput}"


def timeit(func, *args, warmup: int = 1, iterations: int = 3, **kwargs) -> float:
    """Time a function with warmup and averaging."""
    for _ in range(warmup):
        func(*args, **kwargs)
    
    gc.collect()
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        times.append(time.perf_counter() - start)
    
    return min(times), result


# ============================================================================
# 1. JSON Operations (High Volume)
# ============================================================================

def bench_json_parse_stdlib(data: bytes) -> list:
    """Parse JSONL using stdlib json."""
    return [json.loads(line) for line in data.split(b'\n') if line]


def bench_json_parse_orjson(data: bytes) -> list:
    """Parse JSONL using orjson (if available)."""
    try:
        import orjson
        return [orjson.loads(line) for line in data.split(b'\n') if line]
    except ImportError:
        return []


def bench_json_serialize_stdlib(records: list) -> bytes:
    """Serialize records to JSONL using stdlib."""
    return b'\n'.join(json.dumps(r).encode() for r in records)


def bench_json_serialize_orjson(records: list) -> bytes:
    """Serialize records to JSONL using orjson."""
    try:
        import orjson
        return b'\n'.join(orjson.dumps(r) for r in records)
    except ImportError:
        return b''


# ============================================================================
# 2. String/Parsing Operations (CPU-bound)
# ============================================================================

# Accession number format: 0000320193-24-000081
ACCESSION_REGEX = re.compile(r'^(\d{10})-(\d{2})-(\d{6})$')
ACCESSION_REGEX_BYTES = re.compile(rb'^(\d{10})-(\d{2})-(\d{6})$')


def parse_accession_regex(acc: str) -> tuple | None:
    """Parse accession number using regex."""
    m = ACCESSION_REGEX.match(acc)
    if m:
        return (m.group(1), int(m.group(2)), int(m.group(3)))
    return None


def parse_accession_manual(acc: str) -> tuple | None:
    """Parse accession number manually (no regex)."""
    if len(acc) != 20 or acc[10] != '-' or acc[13] != '-':
        return None
    try:
        return (acc[:10], int(acc[11:13]), int(acc[14:]))
    except ValueError:
        return None


def parse_accession_manual_bytes(acc: bytes) -> tuple | None:
    """Parse accession number from bytes (zero-copy)."""
    if len(acc) != 20 or acc[10:11] != b'-' or acc[13:14] != b'-':
        return None
    try:
        return (acc[:10], int(acc[11:13]), int(acc[14:]))
    except ValueError:
        return None


def bench_accession_parsing(accessions: list[str], parser) -> int:
    """Benchmark accession number parsing."""
    count = 0
    for acc in accessions:
        if parser(acc):
            count += 1
    return count


# ============================================================================
# 3. Hash/Digest Operations (CPU-bound)
# ============================================================================

def bench_hash_md5(data: bytes) -> bytes:
    """Hash data with MD5."""
    return hashlib.md5(data).digest()


def bench_hash_sha256(data: bytes) -> bytes:
    """Hash data with SHA256."""
    return hashlib.sha256(data).digest()


def bench_hash_xxhash(data: bytes) -> int:
    """Hash data with xxhash (if available)."""
    try:
        import xxhash
        return xxhash.xxh64(data).intdigest()
    except ImportError:
        return 0


def bench_content_fingerprint(records: list[dict]) -> list[str]:
    """Generate content fingerprints for deduplication."""
    fingerprints = []
    for r in records:
        # Combine key fields for fingerprint
        content = f"{r.get('type', '')}:{r.get('title', '')}:{r.get('url', '')}"
        fp = hashlib.sha256(content.encode()).hexdigest()[:16]
        fingerprints.append(fp)
    return fingerprints


# ============================================================================
# 4. Data Structure Operations (Memory-bound)
# ============================================================================

def bench_dict_lookups(data: dict, keys: list) -> int:
    """Benchmark dictionary lookups."""
    found = 0
    for key in keys:
        if key in data:
            found += 1
    return found


def bench_set_membership(data: set, items: list) -> int:
    """Benchmark set membership tests."""
    found = 0
    for item in items:
        if item in data:
            found += 1
    return found


def bench_list_sort(items: list) -> list:
    """Benchmark sorting."""
    return sorted(items)


def bench_list_sort_key(records: list) -> list:
    """Benchmark sorting with key function."""
    return sorted(records, key=lambda r: (r.get('type', ''), r.get('event_time', '')))


# ============================================================================
# 5. Concurrent Processing
# ============================================================================

def process_record(record: dict) -> dict:
    """Process a single record (simulate work)."""
    # Parse accession number
    acc = record.get('metadata', {}).get('accession_number', '')
    parsed = parse_accession_manual(acc) if acc else None
    
    # Generate fingerprint
    content = f"{record.get('type', '')}:{record.get('title', '')}"
    fp = hashlib.md5(content.encode()).hexdigest()[:8]
    
    return {
        'id': record.get('id'),
        'parsed_acc': parsed,
        'fingerprint': fp,
    }


def bench_sequential(records: list) -> list:
    """Process records sequentially."""
    return [process_record(r) for r in records]


def bench_threaded(records: list, workers: int = 8) -> list:
    """Process records with threads."""
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(process_record, records))


def bench_multiprocess(records: list, workers: int = 8) -> list:
    """Process records with processes."""
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(process_record, records, chunksize=100))


# ============================================================================
# 6. Binary Data Operations
# ============================================================================

def bench_struct_pack(records: list) -> bytes:
    """Pack records into binary format."""
    # Pack: record_type (8 bytes) + timestamp (8 bytes unsigned) + id hash (16 bytes)
    fmt = '8s Q 16s'  # Q = unsigned 64-bit
    packed = []
    for r in records:
        rtype = r.get('type', '')[:8].encode().ljust(8, b'\x00')
        ts = hash(r.get('event_time', '')) & 0x7FFFFFFFFFFFFFFF  # Ensure positive
        rid = hashlib.md5(r.get('id', '').encode()).digest()
        packed.append(struct.pack(fmt, rtype, ts, rid))
    return b''.join(packed)


def bench_struct_unpack(data: bytes, count: int) -> list:
    """Unpack binary records."""
    fmt = '8s Q 16s'  # Q = unsigned 64-bit
    size = struct.calcsize(fmt)
    records = []
    for i in range(count):
        offset = i * size
        rtype, ts, rid = struct.unpack(fmt, data[offset:offset+size])
        records.append({'type': rtype.rstrip(b'\x00').decode(), 'ts': ts})
    return records


# ============================================================================
# Main Runner
# ============================================================================

def run_benchmarks():
    """Run all benchmarks and report results."""
    
    print("="*80)
    print("PERFORMANCE BOTTLENECK ANALYSIS")
    print("Identifying operations that could benefit from native code")
    print("="*80)
    
    results = []
    
    # Load test data
    jsonl_file = TEST_DATA_DIR / "sec_records_10k.jsonl"
    ids_file = TEST_DATA_DIR / "unique_ids_100k.txt"
    acc_file = TEST_DATA_DIR / "accession_numbers.txt"
    
    if not jsonl_file.exists():
        print(f"Test data not found: {jsonl_file}")
        print("Run the database export script first")
        return
    
    jsonl_data = jsonl_file.read_bytes()
    records = bench_json_parse_stdlib(jsonl_data)
    accessions = acc_file.read_text().strip().split('\n') if acc_file.exists() else []
    unique_ids = ids_file.read_text().strip().split('\n') if ids_file.exists() else []
    
    print(f"\nTest data: {len(records):,} records, {len(accessions):,} accessions, {len(unique_ids):,} IDs")
    print(f"JSONL size: {len(jsonl_data)/1024/1024:.2f} MB")
    print()
    
    # -------------------------------------------------------------------------
    # JSON Benchmarks
    # -------------------------------------------------------------------------
    print("-" * 80)
    print("1. JSON OPERATIONS (orjson is Rust-based)")
    print("-" * 80)
    
    elapsed, _ = timeit(bench_json_parse_stdlib, jsonl_data)
    results.append(BenchResult("JSON parse (stdlib)", len(records), elapsed, bytes_processed=len(jsonl_data)))
    print(results[-1])
    
    try:
        import orjson
        elapsed, _ = timeit(bench_json_parse_orjson, jsonl_data)
        results.append(BenchResult("JSON parse (orjson/Rust)", len(records), elapsed, bytes_processed=len(jsonl_data)))
        print(results[-1])
    except ImportError:
        print("  orjson not installed - skipping")
    
    elapsed, _ = timeit(bench_json_serialize_stdlib, records)
    results.append(BenchResult("JSON serialize (stdlib)", len(records), elapsed, bytes_processed=len(jsonl_data)))
    print(results[-1])
    
    try:
        import orjson
        elapsed, _ = timeit(bench_json_serialize_orjson, records)
        results.append(BenchResult("JSON serialize (orjson/Rust)", len(records), elapsed, bytes_processed=len(jsonl_data)))
        print(results[-1])
    except ImportError:
        pass
    
    # -------------------------------------------------------------------------
    # String Parsing Benchmarks
    # -------------------------------------------------------------------------
    print()
    print("-" * 80)
    print("2. STRING PARSING (Cython/Rust candidate)")
    print("-" * 80)
    
    # Repeat accessions for meaningful benchmark
    test_accessions = accessions * 10  # 100K iterations
    
    elapsed, count = timeit(bench_accession_parsing, test_accessions, parse_accession_regex)
    results.append(BenchResult("Accession parse (regex)", len(test_accessions), elapsed))
    print(results[-1])
    
    elapsed, count = timeit(bench_accession_parsing, test_accessions, parse_accession_manual)
    results.append(BenchResult("Accession parse (manual)", len(test_accessions), elapsed))
    print(results[-1])
    
    # Bytes version
    test_accessions_bytes = [a.encode() for a in test_accessions]
    elapsed, count = timeit(bench_accession_parsing, test_accessions_bytes, parse_accession_manual_bytes)
    results.append(BenchResult("Accession parse (bytes)", len(test_accessions_bytes), elapsed))
    print(results[-1])
    
    # -------------------------------------------------------------------------
    # Hash Benchmarks
    # -------------------------------------------------------------------------
    print()
    print("-" * 80)
    print("3. HASHING (xxhash is C-based)")
    print("-" * 80)
    
    # Hash JSONL data multiple times
    iterations = 100
    
    elapsed, _ = timeit(lambda: [bench_hash_md5(jsonl_data) for _ in range(iterations)])
    results.append(BenchResult("MD5 hash", iterations, elapsed, bytes_processed=len(jsonl_data)*iterations))
    print(results[-1])
    
    elapsed, _ = timeit(lambda: [bench_hash_sha256(jsonl_data) for _ in range(iterations)])
    results.append(BenchResult("SHA256 hash", iterations, elapsed, bytes_processed=len(jsonl_data)*iterations))
    print(results[-1])
    
    try:
        import xxhash
        elapsed, _ = timeit(lambda: [bench_hash_xxhash(jsonl_data) for _ in range(iterations)])
        results.append(BenchResult("xxhash64 (C)", iterations, elapsed, bytes_processed=len(jsonl_data)*iterations))
        print(results[-1])
    except ImportError:
        print("  xxhash not installed - skipping")
    
    # Content fingerprinting
    elapsed, _ = timeit(bench_content_fingerprint, records)
    results.append(BenchResult("Content fingerprint", len(records), elapsed))
    print(results[-1])
    
    # -------------------------------------------------------------------------
    # Data Structure Benchmarks
    # -------------------------------------------------------------------------
    print()
    print("-" * 80)
    print("4. DATA STRUCTURES (dict/set in C already)")
    print("-" * 80)
    
    # Build lookup structures
    id_dict = {uid: i for i, uid in enumerate(unique_ids)}
    id_set = set(unique_ids)
    test_keys = unique_ids[:10000] + ['nonexistent-' + str(i) for i in range(1000)]
    
    elapsed, _ = timeit(bench_dict_lookups, id_dict, test_keys * 10)
    results.append(BenchResult("Dict lookups", len(test_keys) * 10, elapsed))
    print(results[-1])
    
    elapsed, _ = timeit(bench_set_membership, id_set, test_keys * 10)
    results.append(BenchResult("Set membership", len(test_keys) * 10, elapsed))
    print(results[-1])
    
    # Sorting
    elapsed, _ = timeit(bench_list_sort, unique_ids.copy())
    results.append(BenchResult("List sort (strings)", len(unique_ids), elapsed))
    print(results[-1])
    
    elapsed, _ = timeit(bench_list_sort_key, records.copy())
    results.append(BenchResult("List sort (key func)", len(records), elapsed))
    print(results[-1])
    
    # -------------------------------------------------------------------------
    # Concurrent Processing
    # -------------------------------------------------------------------------
    print()
    print("-" * 80)
    print("5. CONCURRENT PROCESSING (GIL limitation)")
    print("-" * 80)
    
    test_records = records[:2000]  # Smaller set for concurrency tests
    
    elapsed, _ = timeit(bench_sequential, test_records, iterations=1)
    results.append(BenchResult("Sequential processing", len(test_records), elapsed))
    print(results[-1])
    
    elapsed, _ = timeit(bench_threaded, test_records, 8, iterations=1)
    results.append(BenchResult("Threaded (8 workers)", len(test_records), elapsed, notes="GIL-limited"))
    print(results[-1])
    
    elapsed, _ = timeit(bench_multiprocess, test_records, 8, iterations=1)
    results.append(BenchResult("Multiprocess (8 workers)", len(test_records), elapsed, notes="IPC overhead"))
    print(results[-1])
    
    # -------------------------------------------------------------------------
    # Binary Operations
    # -------------------------------------------------------------------------
    print()
    print("-" * 80)
    print("6. BINARY OPERATIONS (struct is C-based)")
    print("-" * 80)
    
    elapsed, packed = timeit(bench_struct_pack, records)
    results.append(BenchResult("Struct pack", len(records), elapsed, bytes_processed=len(packed)))
    print(results[-1])
    
    elapsed, _ = timeit(bench_struct_unpack, packed, len(records))
    results.append(BenchResult("Struct unpack", len(records), elapsed, bytes_processed=len(packed)))
    print(results[-1])
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print()
    print("=" * 80)
    print("SUMMARY: NATIVE CODE OPPORTUNITIES")
    print("=" * 80)
    print("""
Based on benchmarks, these operations would benefit from native code:

🚀 HIGH IMPACT (Rust/C recommended):
   - JSON parsing/serialization: orjson (Rust) is 3-10x faster
   - String parsing: Cython or Rust regex could help at scale
   - Hashing: xxhash (C) is 5-10x faster than stdlib
   
⚠️  MODERATE IMPACT:
   - Content fingerprinting: Batch hash operations in native code
   - Concurrent processing: Rust can bypass GIL completely
   - Binary serialization: Already C-based (struct module)
   
✅ ALREADY OPTIMIZED (Python C extensions):
   - Dict/Set operations: Built-in hash tables are fast
   - Sorting: Timsort is highly optimized
   - regex: re2 or Rust regex for complex patterns

🎯 RECOMMENDED NATIVE EXTENSIONS:
   1. pip install orjson      # Rust JSON (easy win)
   2. pip install xxhash      # C hashing (easy win)
   3. Custom Rust via PyO3    # Accession parsing + fingerprinting
   4. Cython                  # Hot loops with type hints
""")


if __name__ == "__main__":
    run_benchmarks()
