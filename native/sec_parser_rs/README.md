# SEC Parser - Rust Implementation

This directory contains a high-performance Rust implementation for SEC filing parsing.

## Why Rust?

Based on benchmarks, Python with multiprocessing achieves ~2 GB/s on 24 cores.
Rust can potentially achieve:
- **10+ GB/s** with memory-mapped files + SIMD regex (ripgrep-style)
- **Near-zero allocation** for document splitting
- **Better parallelism** with rayon
- **Single binary** deployment

## Performance Targets

| Operation | Python | Rust Target | Speedup |
|-----------|--------|-------------|---------|
| Document Splitting | 2 GB/s | 10 GB/s | 5x |
| Regex (SIMD) | 2 GB/s | 20 GB/s | 10x |
| JSON Serialize | 50 MB/s | 1 GB/s | 20x |
| Batch Processing | 2 GB/s | 15 GB/s | 7.5x |

## Build

```bash
cd feedspine/native/sec_parser_rs
cargo build --release
```

## Usage

```bash
# Parse single file
./target/release/sec_parser parse /path/to/submission.txt

# Batch process directory
./target/release/sec_parser batch /path/to/sec_data --threads 24

# Benchmark
./target/release/sec_parser bench /path/to/submission.txt --iterations 10
```

## Python Integration (PyO3)

```python
# Coming soon - install with: pip install sec-parser-rs
from sec_parser_rs import parse_submission, batch_parse

result = parse_submission("/path/to/file.txt")
print(f"Found {result.doc_count} documents")
```
