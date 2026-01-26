# Multi-Language Performance Analysis for SEC Data Processing

## Benchmark Results Summary

Tests run on Windows with Python 3.11, 10K SEC records, 100K unique IDs

---

## 🔥 Real-World SEC Filing Results (26MB files)

| Operation | Method A | Method B | Speedup |
|-----------|----------|----------|---------|
| **Document Splitting** | Regex: 92 MB/s | Manual: **3,500 MB/s** | **38x** |
| **Content Hashing** | MD5: 800 MB/s | xxhash: **11,000 MB/s** | **14x** |
| **Metadata Extraction** | Regex: 500K/s | Manual: **1M/s** | **2x** |
| **HTML Parsing** | 88 docs in 0.15s | (lxml is already optimal) | - |

---

### 1. JSON Operations (Data Serialization)

| Operation | stdlib (Python) | orjson (Rust) | Speedup |
|-----------|-----------------|---------------|---------|
| Parse JSONL (8.5 MB) | 139 MB/s | 245 MB/s | **1.8x** |
| Serialize JSONL | 155 MB/s | 530 MB/s | **3.4x** |

**Verdict**: Drop-in replacement. `pip install orjson` = instant win.

### 2. String Parsing (Accession Numbers)

| Method | Throughput | Notes |
|--------|------------|-------|
| Python regex | 1.7M items/s | Compiled regex |
| Python manual | 3.3M items/s | String slicing |
| Python bytes | 3.2M items/s | Zero-copy slicing |
| Cython (est.) | 10-15M items/s | Typed, no bounds checks |
| Rust (est.) | 20-50M items/s | SIMD-friendly, parallel |

**Verdict**: Manual parsing is 2x faster than regex. Cython/Rust worthwhile at 100M+ records.

### 3. Hashing (Content Fingerprinting)

| Algorithm | Throughput | Use Case |
|-----------|------------|----------|
| MD5 (stdlib) | 834 MB/s | Compatibility |
| SHA256 (stdlib) | 1,966 MB/s | Security |
| xxhash64 (C) | **15,796 MB/s** | Speed |
| FNV-1a (Rust) | 20,000+ MB/s | Custom impl |

**Verdict**: xxhash is **19x faster** than MD5. `pip install xxhash` for all non-crypto hashing.

### 4. Data Structures (Lookups)

| Operation | Throughput | Notes |
|-----------|------------|-------|
| Dict lookup | 26M items/s | Python C impl |
| Set membership | 30M items/s | Python C impl |
| List sort (strings) | 73M items/s | Timsort |
| List sort (key func) | 2M items/s | Python callback overhead |

**Verdict**: Already C-optimized. Custom sort keys are the only bottleneck.

### 5. Concurrent Processing

| Method | Throughput | Scaling |
|--------|------------|---------|
| Sequential | 140K items/s | 1x baseline |
| ThreadPool (8) | 65K items/s | **0.5x slower!** |
| ProcessPool (8) | 12K items/s | **0.08x slower!** |

**Verdict**: GIL kills threading for CPU-bound work. IPC overhead kills multiprocessing for small tasks.
→ **Rust releases GIL, enabling true parallelism**

### 6. Binary Operations (Struct)

| Operation | Throughput | Notes |
|-----------|------------|-------|
| Struct pack | 681K items/s (21 MB/s) | C extension |
| Struct unpack | 1.7M items/s (53 MB/s) | C extension |

**Verdict**: Already C-based. Custom binary formats would need Cython/Rust.

---

## Recommended Native Extensions

### Immediate Wins (pip install)

```bash
# Rust-based JSON (3x faster serialize)
pip install orjson

# C-based hashing (19x faster)
pip install xxhash

# Optional: Rust regex for complex patterns
pip install regex  # or rure
```

### Custom Extensions Worth Building

#### 1. Rust Parser Module (PyO3)

```rust
// Parallel accession parsing
fn parse_accession_batch(accessions: Vec<String>) -> Vec<Option<(String, u8, u32)>> {
    accessions.par_iter().map(|acc| parse_accession(acc)).collect()
}

// Parallel document splitting
fn split_documents(data: &[u8]) -> Vec<&[u8]> {
    // Finds <DOCUMENT>...</DOCUMENT> boundaries in parallel
}
```

**Expected speedup**: 5-20x for batch operations (releases GIL + SIMD)

#### 2. Cython Hot Loops

```cython
@cython.boundscheck(False)
@cython.wraparound(False)
def find_document_boundaries_cython(bytes data):
    # 3-5x speedup for tight loops
```

---

## Decision Matrix

| Operation | Volume | Current | Recommendation |
|-----------|--------|---------|----------------|
| JSON parse/serialize | High | stdlib | **orjson** |
| Content hashing | High | MD5 | **xxhash64** |
| Accession parsing | Medium | regex | Manual Python |
| Document splitting | Medium | lxml | lxml (already C) |
| Text extraction | Medium | html2text | lxml.text_content() |
| Set/Dict lookups | High | stdlib | Keep (already C) |
| Parallel processing | High | multiprocessing | **Rust/PyO3** |

---

## File Structure

```
feedspine/benchmarks/
├── language_comparison.py      # Main benchmark runner
├── cython_parsers.pyx          # Cython implementation
├── rust_parsers/               # Rust/PyO3 implementation
│   ├── Cargo.toml
│   └── src/lib.rs
└── test_data/
    ├── sec_records_10k.jsonl   # From capture-spine DB
    ├── unique_ids_100k.txt     # For lookup tests
    └── accession_numbers.txt   # For parsing tests
```

## Building Native Extensions

### Cython

```bash
pip install cython
cd feedspine/benchmarks
cythonize -i cython_parsers.pyx
```

### Rust (via maturin)

```bash
pip install maturin
cd feedspine/benchmarks/rust_parsers
maturin develop --release
```

---

## Key Insights

1. **Manual byte operations crush regex** - 38x faster for document splitting!
2. **Python's stdlib is surprisingly fast** for most operations due to C extensions
3. **orjson is a must-have** - 3x faster JSON with zero code changes
4. **xxhash is a must-have** - 14x faster hashing for deduplication
5. **GIL is the real enemy** - Rust/Cython unlock true parallelism
6. **lxml is already optimal** - No need to replace for HTML parsing
7. **Manual parsing beats regex** - 2x faster for simple patterns

## Next Steps

1. ✅ Install `orjson` and `xxhash` (immediate gains)
2. ✅ Use manual byte operations instead of regex
3. 🔜 Build Rust extension for parallel batch processing
4. 🔜 Profile real workloads to find actual bottlenecks
5. 🔜 Consider Cython for hot loops in existing code
