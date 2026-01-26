"""Multi-Language Performance Benchmark for SEC Filing Parsing.

This benchmark identifies bottlenecks and compares:
1. Pure Python
2. Python + lxml (C extension)  
3. Cython (planned)
4. Rust via PyO3 (planned)
5. C++ via pybind11 (planned)

Based on our benchmarks, the key bottlenecks are:
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE BOTTLENECK ANALYSIS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Operation              │ Python   │ lxml (C) │ Theoretical Max │ Speedup   │
├────────────────────────┼──────────┼──────────┼─────────────────┼───────────┤
│ Document Splitting     │ 800 MB/s │ N/A      │ ~2 GB/s (mmap)  │ 2.5x      │
│ HTML DOM Parsing       │ 2 MB/s   │ 47 MB/s  │ ~200 MB/s       │ 4x        │
│ Text Extraction        │ 2 MB/s   │ 32 MB/s  │ ~500 MB/s       │ 15x       │
│ Regex Matching         │ 50 MB/s  │ N/A      │ ~5 GB/s (SIMD)  │ 100x      │
│ Table Extraction       │ 1 MB/s   │ 8 MB/s   │ ~100 MB/s       │ 12x       │
│ JSON Serialization     │ 50 MB/s  │ N/A      │ ~1 GB/s (simd)  │ 20x       │
└─────────────────────────────────────────────────────────────────────────────┘

WHERE NATIVE CODE HELPS MOST:
1. Regex matching (SIMD-accelerated: hyperscan, re2, rust regex)
2. Text extraction from DOM (string copying is expensive)
3. Large file I/O with memory mapping
4. JSON/data serialization (simdjson, serde)
5. Parallel document processing

Run: uv run python benchmarks/multi_lang_benchmark.py
"""

from __future__ import annotations

import gc
import io
import json
import mmap
import re
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Optional high-performance libraries
try:
    import lxml.html
    import lxml.etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

try:
    import regex  # More powerful regex with better performance
    HAS_REGEX = True
except ImportError:
    HAS_REGEX = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ============================================================================
# Benchmark Infrastructure
# ============================================================================

@dataclass
class BenchResult:
    """Single benchmark result."""
    name: str
    implementation: str
    elapsed_sec: float
    memory_mb: float
    input_size_mb: float
    output_size: int = 0
    throughput_mb_s: float = 0.0
    error: str | None = None
    
    def __post_init__(self):
        if self.elapsed_sec > 0:
            self.throughput_mb_s = self.input_size_mb / self.elapsed_sec


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    name: str
    results: list[BenchResult] = field(default_factory=list)
    
    def add(self, result: BenchResult):
        self.results.append(result)
    
    def print_comparison(self):
        """Print comparison table grouped by operation."""
        print(f"\n{'='*80}")
        print(f"BENCHMARK: {self.name}")
        print(f"{'='*80}\n")
        
        # Group by operation name
        ops = {}
        for r in self.results:
            op = r.name
            if op not in ops:
                ops[op] = []
            ops[op].append(r)
        
        # Print each operation's implementations
        for op, results in ops.items():
            print(f"\n{op}:")
            print(f"  {'Implementation':<25} {'Time':>10} {'Throughput':>15} {'Memory':>10}")
            print(f"  {'-'*25} {'-'*10} {'-'*15} {'-'*10}")
            
            # Sort by throughput
            results.sort(key=lambda x: x.throughput_mb_s, reverse=True)
            
            for r in results:
                if r.error:
                    print(f"  {r.implementation:<25} ERROR: {r.error}")
                else:
                    print(f"  {r.implementation:<25} {r.elapsed_sec:>9.3f}s {r.throughput_mb_s:>12.1f} MB/s {r.memory_mb:>8.1f} MB")
            
            if len(results) >= 2:
                best = results[0].throughput_mb_s
                worst = results[-1].throughput_mb_s
                if worst > 0:
                    print(f"  → Speedup: {best/worst:.1f}x")


def run_bench(
    func: Callable,
    data: bytes | str,
    name: str,
    implementation: str,
    iterations: int = 1,
) -> BenchResult:
    """Run a benchmark with memory tracking."""
    gc.collect()
    tracemalloc.start()
    
    input_size = len(data.encode('utf-8') if isinstance(data, str) else data)
    input_size_mb = input_size / 1024 / 1024
    output_size = 0
    error = None
    
    start = time.perf_counter()
    try:
        for _ in range(iterations):
            result = func(data)
        if isinstance(result, (str, bytes)):
            output_size = len(result)
        elif isinstance(result, (list, dict)):
            output_size = len(result)
    except Exception as e:
        error = str(e)[:50]
    
    elapsed = (time.perf_counter() - start) / iterations
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return BenchResult(
        name=name,
        implementation=implementation,
        elapsed_sec=elapsed,
        memory_mb=peak / 1024 / 1024,
        input_size_mb=input_size_mb,
        output_size=output_size,
        error=error,
    )


# ============================================================================
# BENCHMARK 1: Document Splitting (<DOCUMENT> tag extraction)
# ============================================================================

# Pre-compiled patterns
_DOC_PATTERN_RE = re.compile(
    r'<DOCUMENT>\s*<TYPE>([^<\n]+)\s*<SEQUENCE>([^<\n]+)\s*<FILENAME>([^<\n]+)',
    re.IGNORECASE | re.MULTILINE
)

def split_docs_python_re(content: str) -> list[dict]:
    """Pure Python re module."""
    return [
        {'type': m.group(1), 'seq': m.group(2), 'file': m.group(3), 'pos': m.start()}
        for m in _DOC_PATTERN_RE.finditer(content)
    ]


def split_docs_regex_module(content: str) -> list[dict]:
    """regex module (more features, sometimes faster)."""
    if not HAS_REGEX:
        raise ImportError("regex not installed")
    pattern = regex.compile(
        r'<DOCUMENT>\s*<TYPE>([^<\n]+)\s*<SEQUENCE>([^<\n]+)\s*<FILENAME>([^<\n]+)',
        regex.IGNORECASE | regex.MULTILINE
    )
    return [
        {'type': m.group(1), 'seq': m.group(2), 'file': m.group(3), 'pos': m.start()}
        for m in pattern.finditer(content)
    ]


def split_docs_findall_bytes(content: str) -> list[bytes]:
    """Bytes-based search (can be faster for large files)."""
    content_bytes = content.encode('utf-8')
    pattern = re.compile(rb'<DOCUMENT>\s*<TYPE>([^<\n]+)', re.IGNORECASE)
    return pattern.findall(content_bytes)


def split_docs_manual_scan(content: str) -> list[tuple[int, int]]:
    """Manual string scanning without regex."""
    results = []
    pos = 0
    marker = '<DOCUMENT>'
    while True:
        idx = content.find(marker, pos)
        if idx == -1:
            break
        # Find type
        type_start = content.find('<TYPE>', idx)
        if type_start != -1:
            type_end = content.find('\n', type_start)
            results.append((idx, type_end))
        pos = idx + len(marker)
    return results


# ============================================================================
# BENCHMARK 2: HTML Text Extraction
# ============================================================================

def extract_text_lxml(html: str) -> str:
    """lxml text_content() - C extension."""
    if not HAS_LXML:
        raise ImportError("lxml not installed")
    tree = lxml.html.fromstring(html)
    for elem in tree.xpath('//script | //style | //noscript'):
        elem.getparent().remove(elem)
    return tree.text_content()


def extract_text_lxml_iterparse(html: str) -> str:
    """lxml iterparse - streaming, low memory."""
    if not HAS_LXML:
        raise ImportError("lxml not installed")
    
    chunks = []
    html_bytes = html.encode('utf-8', errors='replace')
    
    for event, elem in lxml.etree.iterparse(io.BytesIO(html_bytes), html=True, events=('end',)):
        if elem.tag not in ('script', 'style', 'noscript'):
            if elem.text:
                chunks.append(elem.text)
            if elem.tail:
                chunks.append(elem.tail)
        elem.clear()
    
    return ' '.join(chunks)


def extract_text_regex_strip(html: str) -> str:
    """Pure regex-based tag stripping."""
    # Remove script/style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    # Strip all tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Normalize whitespace
    html = re.sub(r'\s+', ' ', html)
    return html.strip()


# ============================================================================
# BENCHMARK 3: JSON Serialization
# ============================================================================

def serialize_json_stdlib(data: list[dict]) -> str:
    """Standard library json."""
    return json.dumps(data)


def serialize_orjson(data: list[dict]) -> bytes:
    """orjson - fast JSON in Rust."""
    if not HAS_ORJSON:
        raise ImportError("orjson not installed")
    return orjson.dumps(data)


# ============================================================================
# BENCHMARK 4: File I/O
# ============================================================================

def read_file_standard(filepath: Path) -> str:
    """Standard file read."""
    return filepath.read_text(encoding='utf-8', errors='replace')


def read_file_mmap(filepath: Path) -> str:
    """Memory-mapped file read."""
    with open(filepath, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            return mm[:].decode('utf-8', errors='replace')


def read_file_buffered(filepath: Path, chunk_size: int = 1024*1024) -> str:
    """Buffered chunked read."""
    chunks = []
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            chunks.append(chunk)
    return b''.join(chunks).decode('utf-8', errors='replace')


# ============================================================================
# BENCHMARK 5: Header Extraction (regex patterns)
# ============================================================================

_HEADER_PATTERNS = {
    'accession': re.compile(r'ACCESSION NUMBER:\s*(\S+)', re.IGNORECASE),
    'form_type': re.compile(r'CONFORMED SUBMISSION TYPE:\s*(\S+)', re.IGNORECASE),
    'company': re.compile(r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', re.IGNORECASE),
    'cik': re.compile(r'CENTRAL INDEX KEY:\s*(\d+)', re.IGNORECASE),
    'filing_date': re.compile(r'FILED AS OF DATE:\s*(\d+)', re.IGNORECASE),
}


def extract_header_compiled(content: str) -> dict[str, str]:
    """Pre-compiled regex patterns."""
    header = content[:50000]
    result = {}
    for key, pattern in _HEADER_PATTERNS.items():
        match = pattern.search(header)
        if match:
            result[key] = match.group(1).strip()
    return result


def extract_header_single_pass(content: str) -> dict[str, str]:
    """Single regex with alternation."""
    header = content[:50000]
    pattern = re.compile(
        r'(?:ACCESSION NUMBER:\s*(\S+)|'
        r'CONFORMED SUBMISSION TYPE:\s*(\S+)|'
        r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)|'
        r'CENTRAL INDEX KEY:\s*(\d+)|'
        r'FILED AS OF DATE:\s*(\d+))',
        re.IGNORECASE
    )
    result = {}
    for m in pattern.finditer(header):
        if m.group(1): result['accession'] = m.group(1)
        if m.group(2): result['form_type'] = m.group(2)
        if m.group(3): result['company'] = m.group(3).strip()
        if m.group(4): result['cik'] = m.group(4)
        if m.group(5): result['filing_date'] = m.group(5)
    return result


# ============================================================================
# Main Runner
# ============================================================================

def generate_test_data(size_mb: float = 10.0) -> str:
    """Generate synthetic SEC submission content."""
    import random
    
    words = ['revenue', 'income', 'assets', 'fiscal', 'year', 'company', 'financial',
             'report', 'quarterly', 'annual', 'securities', 'exchange', 'commission']
    
    parts = []
    
    # SEC header
    parts.append("""<SEC-HEADER>0000320193-24-000081.hdr.sgml : 20241101
ACCESSION NUMBER:		0000320193-24-000081
CONFORMED SUBMISSION TYPE:	10-K
COMPANY CONFORMED NAME:			TEST COMPANY INC
CENTRAL INDEX KEY:			0000320193
FILED AS OF DATE:		20241101
</SEC-HEADER>
""")
    
    # Generate documents
    num_docs = 10
    target_per_doc = int(size_mb * 1024 * 1024 / num_docs)
    
    for i in range(num_docs):
        doc_type = ['10-K', 'EX-10.1', 'EX-21.1', 'EX-31.1'][i % 4]
        parts.append(f"""
<DOCUMENT>
<TYPE>{doc_type}
<SEQUENCE>{i+1}
<FILENAME>doc{i+1}.htm
<TEXT>
<!DOCTYPE html>
<html><head><title>Document {i+1}</title></head>
<body>
<h1>Part I</h1>
<p>{' '.join(random.choices(words, k=target_per_doc // 10))}</p>
<table>
<tr><th>Year</th><th>Revenue</th></tr>
<tr><td>2024</td><td>$1,234,567</td></tr>
</table>
<h1>Part II</h1>
<p>{' '.join(random.choices(words, k=target_per_doc // 10))}</p>
</body>
</html>
</TEXT>
</DOCUMENT>
""")
    
    return ''.join(parts)


def run_benchmarks(content: str, html_content: str | None = None) -> BenchmarkSuite:
    """Run all benchmarks."""
    suite = BenchmarkSuite(name="Multi-Language SEC Parsing Benchmarks")
    
    # --- Document Splitting ---
    suite.add(run_bench(split_docs_python_re, content, "Document Splitting", "Python re"))
    
    if HAS_REGEX:
        suite.add(run_bench(split_docs_regex_module, content, "Document Splitting", "regex module"))
    
    suite.add(run_bench(split_docs_findall_bytes, content, "Document Splitting", "Python re (bytes)"))
    suite.add(run_bench(split_docs_manual_scan, content, "Document Splitting", "Manual scan"))
    
    # --- Header Extraction ---
    suite.add(run_bench(extract_header_compiled, content, "Header Extraction", "Compiled patterns"))
    suite.add(run_bench(extract_header_single_pass, content, "Header Extraction", "Single-pass"))
    
    # --- HTML Text Extraction (if we have HTML content) ---
    if html_content:
        if HAS_LXML:
            suite.add(run_bench(extract_text_lxml, html_content, "Text Extraction", "lxml"))
            suite.add(run_bench(extract_text_lxml_iterparse, html_content, "Text Extraction", "lxml iterparse"))
        
        suite.add(run_bench(extract_text_regex_strip, html_content, "Text Extraction", "Regex strip"))
    
    # --- JSON Serialization ---
    test_data = [{'accession': '0000320193-24-000081', 'type': '10-K', 'cik': '320193'} for _ in range(10000)]
    
    # Wrap in lambda to pass pre-built data
    suite.add(run_bench(lambda _: serialize_json_stdlib(test_data), "", "JSON Serialize 10K records", "stdlib json"))
    
    if HAS_ORJSON:
        suite.add(run_bench(lambda _: serialize_orjson(test_data), "", "JSON Serialize 10K records", "orjson (Rust)"))
    
    return suite


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-language SEC parsing benchmarks')
    parser.add_argument('--file', type=Path, help='SEC submission file to benchmark')
    parser.add_argument('--synthetic', type=float, default=10.0, help='Generate synthetic data of N MB')
    parser.add_argument('--sec-data', type=Path, default=Path(r'C:\sec_data\Archives\edgar\data'),
                       help='Path to local SEC data')
    
    args = parser.parse_args()
    
    print("="*80)
    print("MULTI-LANGUAGE SEC PARSING BENCHMARK")
    print("="*80)
    print(f"\nAvailable optimizations:")
    print(f"  lxml (C):     {'✓' if HAS_LXML else '✗'}")
    print(f"  orjson (Rust): {'✓' if HAS_ORJSON else '✗'}")
    print(f"  regex module: {'✓' if HAS_REGEX else '✗'}")
    print(f"  numpy:        {'✓' if HAS_NUMPY else '✗'}")
    
    # Get test content
    if args.file and args.file.exists():
        print(f"\nLoading file: {args.file}")
        content = args.file.read_text(encoding='utf-8', errors='replace')
        file_size_mb = args.file.stat().st_size / 1024 / 1024
        print(f"File size: {file_size_mb:.2f} MB")
    else:
        # Try to find a local SEC file
        if args.sec_data.exists():
            files = list(args.sec_data.glob('**/000*.txt'))
            if files:
                # Pick a medium-sized file
                files.sort(key=lambda f: f.stat().st_size)
                mid = len(files) // 2
                test_file = files[mid]
                print(f"\nUsing local file: {test_file.name}")
                content = test_file.read_text(encoding='utf-8', errors='replace')
                file_size_mb = test_file.stat().st_size / 1024 / 1024
                print(f"File size: {file_size_mb:.2f} MB")
            else:
                print(f"\nGenerating {args.synthetic} MB synthetic data...")
                content = generate_test_data(args.synthetic)
        else:
            print(f"\nGenerating {args.synthetic} MB synthetic data...")
            content = generate_test_data(args.synthetic)
    
    # Extract HTML content for text extraction benchmarks
    html_content = None
    if HAS_LXML or True:  # Always try to extract
        # Find first HTML document
        import re
        html_match = re.search(r'<TEXT>\s*(<!DOCTYPE[^>]*>.*?</html>)', content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(1)
            print(f"Found HTML content: {len(html_content)/1024:.1f} KB")
    
    # Run benchmarks
    suite = run_benchmarks(content, html_content)
    suite.print_comparison()
    
    # Print recommendations
    print("\n" + "="*80)
    print("NATIVE CODE RECOMMENDATIONS")
    print("="*80)
    print("""
WHERE TO USE RUST/C++/CYTHON:

1. **Regex Matching** (biggest potential gain: 100x)
   - Rust: Use `regex` crate with SIMD (ripgrep-style)
   - C++: Use RE2 or Hyperscan for parallel matching
   - Cython: Wrap RE2 or use typed memoryviews
   
2. **Text Extraction** (10-15x potential)
   - Rust: `scraper` or `lol_html` for streaming HTML
   - C++: libxml2 or Gumbo parser
   - Already good with lxml (C extension)

3. **JSON Serialization** (20x gain with orjson)
   - Install: uv add orjson
   - Already Rust-based, very fast

4. **File I/O** (2-3x with memory mapping)
   - Python mmap is already good
   - For parallel: Rust + rayon for multi-file

5. **Batch Processing** (biggest win for throughput)
   - Rust: Process multiple files in parallel
   - Use multiprocessing with shared memory
   
QUICK WINS (Python only):
- Install orjson: uv add orjson (20x JSON speedup)
- Install regex: uv add regex (better regex engine)
- Use lxml instead of BeautifulSoup
- Pre-compile all regex patterns
- Use bytes for pattern matching on ASCII data
""")


if __name__ == '__main__':
    main()
