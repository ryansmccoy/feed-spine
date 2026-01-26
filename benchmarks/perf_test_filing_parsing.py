"""Performance benchmarks for SEC filing parsing and extraction.

Tests py-sec-edgar and FeedSpine's ability to parse actual SEC filings.
Identifies bottlenecks in HTML/SGML parsing, text extraction, and section detection.

KEY WORKFLOW: Complete submission files (.txt) are SGML containers with multiple
<DOCUMENT> sections. They must be SPLIT FIRST using CompleteSubmissionProcessor
before parsing individual documents.

BENCHMARK STAGES:
1. File Loading - Read raw bytes, detect encoding
2. Document Splitting - Extract <DOCUMENT> boundaries (regex-based)
3. Individual Document Parsing - Parse each extracted document

IDENTIFIED BOTTLENECKS (from code analysis):

1. **Complete Submission Splitting** - First critical stage
   - Large files (127MB) must be scanned for <DOCUMENT> tags
   - Regex finditer over entire content
   - Memory: entire file loaded at once
   
2. **BeautifulSoup Parsing** (html_extractor.py, html_processing.py)
   - Full DOM construction for each document
   - Memory-intensive for large HTML documents
   - Parser fallback chain (lxml → html.parser)
   
3. **Regex Pattern Matching** (section_parser.py, patterns.py)
   - Re-compiling patterns on each parse
   - Greedy patterns on large strings
   - Multiple passes over content
   
4. **HTML-to-Text Conversion** (html2text, get_text())
   - Full tree traversal
   - String concatenation overhead
   
5. **Table Extraction** (section_parser._remove_tables)
   - Iterating all tables to check TOC
   - Text extraction for each table
   
6. **SEC Header Parsing** (header.py)
   - Line-by-line regex matching
   - Multiple pattern searches

7. **Memory Accumulation**
   - Loading entire filing into memory
   - Creating multiple string copies during cleaning

Run: python benchmarks/perf_test_filing_parsing.py --file <COMPLETE_SUBMISSION_FILE>
"""

from __future__ import annotations

import asyncio
import gc
import io
import re
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

# Check for optional dependencies
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import lxml.html
    import lxml.etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ============================================================================
# Benchmark Infrastructure
# ============================================================================

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    elapsed_seconds: float
    memory_peak_mb: float
    memory_current_mb: float
    input_size_bytes: int
    output_size: int  # Could be chars, records, sections, etc.
    throughput_mb_per_sec: float = 0.0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.elapsed_seconds > 0 and self.input_size_bytes > 0:
            self.throughput_mb_per_sec = (self.input_size_bytes / 1024 / 1024) / self.elapsed_seconds
    
    def __str__(self) -> str:
        if self.error:
            return f"{self.name}: ERROR - {self.error}"
        return (
            f"{self.name}:\n"
            f"  Time: {self.elapsed_seconds:.3f}s\n"
            f"  Memory Peak: {self.memory_peak_mb:.1f}MB\n"
            f"  Input: {self.input_size_bytes/1024/1024:.2f}MB\n"
            f"  Throughput: {self.throughput_mb_per_sec:.2f} MB/s"
        )


@dataclass  
class BenchmarkSuite:
    """Collection of benchmark results."""
    name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    
    def add(self, result: BenchmarkResult):
        self.results.append(result)
    
    def print_summary(self):
        print(f"\n{'='*70}")
        print(f"Benchmark Suite: {self.name}")
        print(f"{'='*70}\n")
        
        for result in self.results:
            print(result)
            print()
        
        # Find bottlenecks (slowest by throughput)
        valid_results = [r for r in self.results if not r.error and r.throughput_mb_per_sec > 0]
        if valid_results:
            slowest = sorted(valid_results, key=lambda r: r.throughput_mb_per_sec)[:3]
            print("\n" + "="*70)
            print("BOTTLENECKS (slowest throughput):")
            print("="*70)
            for i, r in enumerate(slowest, 1):
                print(f"  {i}. {r.name}: {r.throughput_mb_per_sec:.2f} MB/s")


def benchmark(func: Callable, content: bytes | str, name: str, **kwargs) -> BenchmarkResult:
    """Run a benchmark with memory tracking."""
    gc.collect()
    tracemalloc.start()
    
    input_size = len(content.encode('utf-8') if isinstance(content, str) else content)
    output_size = 0
    error = None
    details = {}
    
    start = time.perf_counter()
    try:
        result = func(content, **kwargs)
        if isinstance(result, str):
            output_size = len(result)
        elif isinstance(result, (list, tuple)):
            output_size = len(result)
        elif isinstance(result, dict):
            output_size = len(result)
            details = {k: type(v).__name__ for k, v in result.items()}
        elif result is not None:
            output_size = 1
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:100]}"
    
    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return BenchmarkResult(
        name=name,
        elapsed_seconds=elapsed,
        memory_peak_mb=peak / 1024 / 1024,
        memory_current_mb=current / 1024 / 1024,
        input_size_bytes=input_size,
        output_size=output_size,
        error=error,
        details=details,
    )


# ============================================================================
# Parsing Benchmarks
# ============================================================================

def bench_bs4_lxml(html: str) -> BeautifulSoup:
    """Benchmark BeautifulSoup with lxml parser."""
    return BeautifulSoup(html, 'lxml')


def bench_bs4_html_parser(html: str) -> BeautifulSoup:
    """Benchmark BeautifulSoup with html.parser."""
    return BeautifulSoup(html, 'html.parser')


def bench_lxml_parse(html: str) -> Any:
    """Benchmark direct lxml parsing."""
    return lxml.html.fromstring(html)


def bench_lxml_iterparse(html: str) -> int:
    """Benchmark lxml iterparse for streaming."""
    # Convert to bytes for iterparse
    html_bytes = html.encode('utf-8', errors='replace')
    count = 0
    for event, elem in lxml.etree.iterparse(io.BytesIO(html_bytes), html=True):
        count += 1
        elem.clear()  # Free memory as we go
    return count


def bench_get_text_bs4(html: str) -> str:
    """Benchmark text extraction with BeautifulSoup."""
    soup = BeautifulSoup(html, 'lxml')
    return soup.get_text(separator=' ')


def bench_get_text_lxml(html: str) -> str:
    """Benchmark text extraction with lxml."""
    tree = lxml.html.fromstring(html)
    return tree.text_content()


def bench_html2text_convert(html: str) -> str:
    """Benchmark html2text conversion."""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html)


def bench_regex_cleanup(html: str) -> str:
    """Benchmark regex-based HTML cleanup."""
    # Common SEC filing cleanup patterns
    patterns = [
        (re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<!--.*?-->', re.DOTALL), ''),
        (re.compile(r'<[^>]+>'), ''),  # Strip all tags
        (re.compile(r'\s+'), ' '),  # Normalize whitespace
    ]
    
    result = html
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)
    return result.strip()


def bench_section_detection(text: str) -> list[tuple[int, str]]:
    """Benchmark section header detection in filing."""
    # Patterns for 10-K/10-Q sections
    patterns = [
        re.compile(r'(?i)(?:^|\n)\s*(PART\s+[IVX]+)', re.MULTILINE),
        re.compile(r'(?i)(?:^|\n)\s*(ITEM\s+\d+[A-Z]?\.?\s*[-–—]?\s*[A-Z][^.\n]{5,100})', re.MULTILINE),
        re.compile(r'(?i)(?:^|\n)\s*(SIGNATURES)', re.MULTILINE),
        re.compile(r'(?i)(?:^|\n)\s*(EXHIBIT\s+INDEX)', re.MULTILINE),
    ]
    
    matches = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            matches.append((match.start(), match.group(1)))
    
    return sorted(matches, key=lambda x: x[0])


def bench_table_extraction_bs4(html: str) -> list[list[list[str]]]:
    """Benchmark table extraction with BeautifulSoup."""
    soup = BeautifulSoup(html, 'lxml')
    tables = []
    
    for table in soup.find_all('table'):
        rows = []
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    
    return tables


def bench_table_extraction_lxml(html: str) -> list[list[list[str]]]:
    """Benchmark table extraction with lxml."""
    tree = lxml.html.fromstring(html)
    tables = []
    
    for table in tree.xpath('//table'):
        rows = []
        for tr in table.xpath('.//tr'):
            cells = [
                ''.join(td.itertext()).strip() 
                for td in tr.xpath('.//td | .//th')
            ]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    
    return tables


def bench_document_splitting(content: str) -> list[dict[str, Any]]:
    """Benchmark SEC complete submission splitting into individual documents.
    
    This is the FIRST critical step - complete submission files contain multiple
    <DOCUMENT> sections that must be extracted before parsing.
    """
    # SEC SGML format patterns (matching CompleteSubmissionProcessor)
    doc_start_pattern = re.compile(
        r'<DOCUMENT>\s*<TYPE>([^<\n]+)\s*<SEQUENCE>([^<\n]+)\s*<FILENAME>([^<\n]+)(?:\s*<DESCRIPTION>([^<\n]+))?',
        re.IGNORECASE | re.MULTILINE
    )
    doc_end_pattern = re.compile(r'</DOCUMENT>', re.IGNORECASE)
    
    documents = []
    doc_matches = list(doc_start_pattern.finditer(content))
    
    for i, match in enumerate(doc_matches):
        doc_type = match.group(1).strip()
        sequence = match.group(2).strip()
        filename = match.group(3).strip()
        description = match.group(4).strip() if match.group(4) else ""
        
        start_pos = match.end()
        
        # Find document end
        if i + 1 < len(doc_matches):
            end_pos = doc_matches[i + 1].start()
        else:
            end_match = doc_end_pattern.search(content, start_pos)
            end_pos = end_match.start() if end_match else len(content)
        
        doc_content = content[start_pos:end_pos].strip()
        
        documents.append({
            'type': doc_type,
            'sequence': sequence,
            'filename': filename,
            'description': description,
            'size': len(doc_content),
            'start': start_pos,
            'end': end_pos,
            'content': doc_content,  # Store actual content for further processing
        })
    
    return documents


def bench_document_splitting_lazy(content: str) -> list[dict[str, Any]]:
    """Benchmark lazy document splitting - metadata only, no content extraction.
    
    This is faster when you only need document list/metadata, not actual content.
    """
    doc_start_pattern = re.compile(
        r'<DOCUMENT>\s*<TYPE>([^<\n]+)\s*<SEQUENCE>([^<\n]+)\s*<FILENAME>([^<\n]+)(?:\s*<DESCRIPTION>([^<\n]+))?',
        re.IGNORECASE | re.MULTILINE
    )
    doc_end_pattern = re.compile(r'</DOCUMENT>', re.IGNORECASE)
    
    documents = []
    doc_matches = list(doc_start_pattern.finditer(content))
    
    for i, match in enumerate(doc_matches):
        start_pos = match.end()
        
        if i + 1 < len(doc_matches):
            end_pos = doc_matches[i + 1].start()
        else:
            end_match = doc_end_pattern.search(content, start_pos)
            end_pos = end_match.start() if end_match else len(content)
        
        documents.append({
            'type': match.group(1).strip(),
            'sequence': match.group(2).strip(),
            'filename': match.group(3).strip(),
            'size': end_pos - start_pos,  # Compute size without extracting content
            'start': start_pos,
            'end': end_pos,
        })
    
    return documents


def bench_full_submission_workflow(content: str) -> dict[str, Any]:
    """Benchmark the complete real-world workflow for processing SEC submissions.
    
    Workflow:
    1. Extract header/metadata
    2. Split into documents
    3. Parse each HTML document
    4. Extract text and sections from primary document
    """
    results = {
        'header': {},
        'documents': [],
        'primary_doc': None,
        'sections': [],
        'total_text_chars': 0,
    }
    
    # Step 1: Extract header (fast, only first 50KB)
    results['header'] = bench_header_extraction(content)
    
    # Step 2: Split into documents
    documents = bench_document_splitting(content)
    results['documents'] = [
        {'type': d['type'], 'filename': d['filename'], 'size': d['size']}
        for d in documents
    ]
    
    # Step 3: Find and parse primary document (10-K, 10-Q, 8-K, etc.)
    primary_types = {'10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '8-K/A', 'DEF 14A'}
    primary_doc = None
    
    for doc in documents:
        if doc['type'].upper() in primary_types:
            primary_doc = doc
            break
        # Also check for htm/html files
        if doc['filename'].lower().endswith(('.htm', '.html')) and primary_doc is None:
            primary_doc = doc
    
    if primary_doc and HAS_BS4:
        # Step 4: Parse the primary document
        doc_content = primary_doc['content']
        
        # Only parse if it looks like HTML
        if '<html' in doc_content.lower() or '<body' in doc_content.lower():
            try:
                soup = BeautifulSoup(doc_content, 'lxml')
                text = soup.get_text(separator='\n')
                results['primary_doc'] = {
                    'type': primary_doc['type'],
                    'filename': primary_doc['filename'],
                    'text_chars': len(text),
                }
                results['total_text_chars'] = len(text)
                
                # Step 5: Detect sections
                results['sections'] = bench_section_detection(text)
            except Exception as e:
                results['primary_doc'] = {'error': str(e)}
    
    return results


def bench_header_extraction(content: str) -> dict[str, str]:
    """Benchmark SEC header extraction."""
    # Extract SEC-HEADER section
    header_pattern = re.compile(
        r'<SEC-HEADER>(.*?)</SEC-HEADER>|'
        r'<IMS-HEADER>(.*?)</IMS-HEADER>|'
        r'ACCESSION NUMBER:\s*(\S+)|'
        r'CONFORMED SUBMISSION TYPE:\s*(\S+)|'
        r'FILED AS OF DATE:\s*(\d+)|'
        r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)',
        re.DOTALL | re.IGNORECASE
    )
    
    metadata = {}
    for match in header_pattern.finditer(content[:50000]):  # Only check first 50KB
        groups = match.groups()
        if groups[0]:
            metadata['sec_header'] = groups[0][:1000]
        # Extract individual fields
    
    # Additional field extraction
    field_patterns = {
        'accession_number': r'ACCESSION NUMBER:\s*(\S+)',
        'form_type': r'CONFORMED SUBMISSION TYPE:\s*(\S+)',
        'filing_date': r'FILED AS OF DATE:\s*(\d+)',
        'company_name': r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)',
        'cik': r'CENTRAL INDEX KEY:\s*(\d+)',
        'sic': r'STANDARD INDUSTRIAL CLASSIFICATION:\s*(.+?)(?:\n|$)',
    }
    
    for field, pattern in field_patterns.items():
        match = re.search(pattern, content[:50000], re.IGNORECASE)
        if match:
            metadata[field] = match.group(1).strip()
    
    return metadata


def bench_xbrl_detection(content: str) -> dict[str, Any]:
    """Benchmark XBRL content detection."""
    results = {
        'has_xbrl': False,
        'has_inline_xbrl': False,
        'xbrl_files': [],
        'namespaces': [],
    }
    
    # Check for XBRL indicators
    if 'xmlns:xbrli' in content or '<xbrli:' in content:
        results['has_xbrl'] = True
    
    if 'xmlns:ix' in content or '<ix:' in content:
        results['has_inline_xbrl'] = True
    
    # Find XBRL file references
    xbrl_pattern = re.compile(r'<FILENAME>([^<]+\.(?:xml|xsd|xbrl))', re.IGNORECASE)
    results['xbrl_files'] = xbrl_pattern.findall(content)
    
    # Extract namespaces
    ns_pattern = re.compile(r'xmlns:(\w+)="([^"]+)"')
    results['namespaces'] = list(set(ns_pattern.findall(content[:100000])))
    
    return results


# ============================================================================
# End-to-End Pipeline Benchmarks
# ============================================================================

def bench_full_parse_pipeline(html: str) -> dict[str, Any]:
    """Benchmark complete parsing pipeline."""
    # 1. Parse HTML
    soup = BeautifulSoup(html, 'lxml')
    
    # 2. Remove scripts/styles
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    
    # 3. Extract text
    text = soup.get_text(separator='\n')
    
    # 4. Clean whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    # 5. Detect sections
    sections = bench_section_detection(text)
    
    # 6. Extract metadata
    metadata = {
        'title': soup.title.string if soup.title else None,
        'word_count': len(text.split()),
        'section_count': len(sections),
    }
    
    return {
        'text': text,
        'sections': sections,
        'metadata': metadata,
    }


def bench_streaming_parse(html: str) -> dict[str, int]:
    """Benchmark memory-efficient streaming parse."""
    stats = {
        'elements': 0,
        'text_chars': 0,
        'tables': 0,
    }
    
    html_bytes = html.encode('utf-8', errors='replace')
    
    for event, elem in lxml.etree.iterparse(io.BytesIO(html_bytes), html=True, events=('end',)):
        stats['elements'] += 1
        
        if elem.tag == 'table':
            stats['tables'] += 1
        
        if elem.text:
            stats['text_chars'] += len(elem.text)
        if elem.tail:
            stats['text_chars'] += len(elem.tail)
        
        # Clear to free memory
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    
    return stats


# ============================================================================
# Main Runner
# ============================================================================

async def fetch_sec_filing(url: str) -> str:
    """Fetch a SEC filing from URL."""
    if not HAS_HTTPX:
        raise ImportError("httpx required: pip install httpx")
    
    # SEC requires a proper User-Agent with contact info
    headers = {
        'User-Agent': 'py-sec-edgar/1.0 (github.com/ryansmccoy/py-sec-edgar; performance-testing)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    async with httpx.AsyncClient(
        headers=headers,
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def run_parsing_benchmarks(content: str, suite_name: str = "SEC Filing Parsing") -> BenchmarkSuite:
    """Run all parsing benchmarks on content."""
    suite = BenchmarkSuite(name=suite_name)
    
    # ==========================================================
    # STAGE 1: Complete Submission Splitting (CRITICAL FIRST STEP)
    # ==========================================================
    suite.add(benchmark(bench_document_splitting, content, "1. Document splitting (full)"))
    suite.add(benchmark(bench_document_splitting_lazy, content, "1. Document splitting (lazy/metadata)"))
    suite.add(benchmark(bench_header_extraction, content, "1. SEC header extraction"))
    suite.add(benchmark(bench_xbrl_detection, content, "1. XBRL detection"))
    
    # Extract documents for per-document benchmarks
    documents = bench_document_splitting(content)
    
    # Find a representative HTML document to benchmark individual parsing
    html_doc = None
    for doc in documents:
        if doc['filename'].lower().endswith(('.htm', '.html')):
            if len(doc['content']) > 1000:  # Skip tiny files
                html_doc = doc
                break
    
    # If no HTML document found, fall back to content if it looks like HTML
    if html_doc is None and ('<html' in content.lower() or '<body' in content.lower()):
        html_doc = {'content': content, 'filename': 'full_content', 'size': len(content)}
    
    if html_doc:
        doc_content = html_doc['content']
        doc_name = html_doc['filename']
        doc_size_mb = len(doc_content) / 1024 / 1024
        
        print(f"\n  >>> Using {doc_name} ({doc_size_mb:.2f}MB) for HTML parsing benchmarks <<<\n")
        
        # ==========================================================
        # STAGE 2: Individual Document HTML Parsing
        # ==========================================================
        if HAS_BS4:
            suite.add(benchmark(bench_bs4_lxml, doc_content, f"2. BeautifulSoup + lxml ({doc_name})"))
            suite.add(benchmark(bench_bs4_html_parser, doc_content, f"2. BeautifulSoup + html.parser ({doc_name})"))
            suite.add(benchmark(bench_get_text_bs4, doc_content, f"2. Text extraction BS4 ({doc_name})"))
            suite.add(benchmark(bench_table_extraction_bs4, doc_content, f"2. Table extraction BS4 ({doc_name})"))
        
        if HAS_LXML:
            suite.add(benchmark(bench_lxml_parse, doc_content, f"2. lxml direct parse ({doc_name})"))
            suite.add(benchmark(bench_lxml_iterparse, doc_content, f"2. lxml iterparse/streaming ({doc_name})"))
            suite.add(benchmark(bench_get_text_lxml, doc_content, f"2. Text extraction lxml ({doc_name})"))
            suite.add(benchmark(bench_table_extraction_lxml, doc_content, f"2. Table extraction lxml ({doc_name})"))
        
        if HAS_HTML2TEXT:
            suite.add(benchmark(bench_html2text_convert, doc_content, f"2. html2text conversion ({doc_name})"))
        
        suite.add(benchmark(bench_regex_cleanup, doc_content, f"2. Regex HTML cleanup ({doc_name})"))
        
        # ==========================================================
        # STAGE 3: Content Analysis (after HTML → text)
        # ==========================================================
        if HAS_BS4:
            soup = BeautifulSoup(doc_content, 'lxml')
            text = soup.get_text()
            suite.add(benchmark(bench_section_detection, text, f"3. Section detection ({doc_name})"))
    else:
        print("\n  >>> No HTML document found - running benchmarks on raw content <<<\n")
        
        # Fall back to regex-based benchmarks on raw content
        suite.add(benchmark(bench_regex_cleanup, content, "Regex HTML cleanup (raw)"))
    
    # ==========================================================
    # STAGE 4: Full End-to-End Pipeline
    # ==========================================================
    suite.add(benchmark(bench_full_submission_workflow, content, "4. Full submission workflow"))
    
    if HAS_BS4 and HAS_LXML and html_doc:
        suite.add(benchmark(bench_full_parse_pipeline, html_doc['content'], f"4. Full parse pipeline ({doc_name})"))
        suite.add(benchmark(bench_streaming_parse, html_doc['content'], f"4. Streaming parse ({doc_name})"))
    
    # Document summary
    print(f"\n  Document Summary:")
    print(f"  - Total documents in submission: {len(documents)}")
    for i, doc in enumerate(documents[:10]):  # Show first 10
        print(f"    {i+1}. {doc['type']:20s} {doc['filename']:40s} ({doc['size']/1024:.1f}KB)")
    if len(documents) > 10:
        print(f"    ... and {len(documents) - 10} more documents")
    
    return suite


def run_multi_file_benchmark(file_paths: list[Path]) -> None:
    """Benchmark across multiple files."""
    print(f"\n{'='*70}")
    print(f"Multi-File Benchmark: {len(file_paths)} files")
    print(f"{'='*70}\n")
    
    total_bytes = 0
    total_time = 0
    
    for path in file_paths:
        content = path.read_text(encoding='utf-8', errors='replace')
        size_mb = len(content.encode('utf-8')) / 1024 / 1024
        total_bytes += len(content.encode('utf-8'))
        
        start = time.perf_counter()
        try:
            if HAS_BS4:
                soup = BeautifulSoup(content, 'lxml')
                text = soup.get_text()
                sections = bench_section_detection(text)
                elapsed = time.perf_counter() - start
                total_time += elapsed
                
                print(f"  {path.name}: {size_mb:.2f}MB → {len(text)/1024:.0f}KB text, "
                      f"{len(sections)} sections in {elapsed:.2f}s")
        except Exception as e:
            print(f"  {path.name}: ERROR - {e}")
    
    if total_time > 0:
        print(f"\nTotal: {total_bytes/1024/1024:.1f}MB in {total_time:.2f}s "
              f"({total_bytes/1024/1024/total_time:.1f} MB/s)")


# Sample SEC filing URLs for testing
SAMPLE_FILINGS = {
    '10-K-small': 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm',
    '10-K-large': 'https://www.sec.gov/Archives/edgar/data/789019/000156459024004539/msft-10k_20240630.htm',
    '8-K': 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000008/aapl-20250102.htm',
    '10-Q': 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000081/aapl-20240629.htm',
}


def generate_synthetic_filing(size_mb: float = 1.0, tables: int = 50, sections: int = 20) -> str:
    """Generate a synthetic SEC-like HTML filing for benchmarking."""
    import random
    
    # Lorem ipsum-ish text
    words = [
        "the", "company", "fiscal", "year", "ended", "revenue", "operating", "income",
        "net", "assets", "liabilities", "stockholders", "equity", "cash", "flow",
        "management", "discussion", "analysis", "financial", "condition", "results",
        "operations", "risk", "factors", "market", "competition", "regulatory",
        "compliance", "securities", "exchange", "commission", "quarterly", "report",
        "annual", "filing", "form", "item", "part", "business", "properties", "legal",
        "proceedings", "executive", "compensation", "directors", "officers", "shares",
        "stock", "dividends", "earnings", "per", "share", "segment", "reporting",
        "consolidated", "statements", "balance", "sheet", "comprehensive", "changes",
    ]
    
    def random_text(word_count: int) -> str:
        return ' '.join(random.choices(words, k=word_count))
    
    def random_number() -> str:
        return f"${random.randint(1, 999)},{random.randint(100, 999)},{random.randint(100, 999)}"
    
    # Build HTML structure
    parts = ['<!DOCTYPE html><html><head><title>Form 10-K</title></head><body>']
    
    # SEC Header section
    parts.append('<div class="sec-header">')
    parts.append('<pre>CONFORMED SUBMISSION TYPE: 10-K\n')
    parts.append('FILED AS OF DATE: 20240928\n')
    parts.append('ACCESSION NUMBER: 0000320193-24-000123\n')
    parts.append('COMPANY CONFORMED NAME: SYNTHETIC CORP\n')
    parts.append('CENTRAL INDEX KEY: 0000320193\n')
    parts.append('</pre></div>')
    
    # Generate sections (Parts/Items)
    part_names = ['PART I', 'PART II', 'PART III', 'PART IV']
    item_names = [
        'Item 1. Business', 'Item 1A. Risk Factors', 'Item 1B. Unresolved Staff Comments',
        'Item 2. Properties', 'Item 3. Legal Proceedings', 'Item 4. Mine Safety Disclosures',
        'Item 5. Market for Registrant Common Equity', 'Item 6. Selected Financial Data',
        'Item 7. Management Discussion and Analysis', 'Item 7A. Quantitative and Qualitative Disclosures',
        'Item 8. Financial Statements', 'Item 9. Changes in and Disagreements with Accountants',
        'Item 9A. Controls and Procedures', 'Item 9B. Other Information',
        'Item 10. Directors and Executive Officers', 'Item 11. Executive Compensation',
    ]
    
    # Calculate content needed per section to reach target size
    target_chars = int(size_mb * 1024 * 1024)
    chars_per_section = target_chars // (len(item_names) + tables)
    words_per_section = chars_per_section // 6  # ~6 chars per word avg
    
    current_part = 0
    for i, item_name in enumerate(item_names):
        if i % 4 == 0 and current_part < len(part_names):
            parts.append(f'<h1>{part_names[current_part]}</h1>')
            current_part += 1
        
        parts.append(f'<h2>{item_name}</h2>')
        parts.append(f'<p>{random_text(words_per_section)}</p>')
    
    # Generate tables
    for t in range(tables):
        parts.append('<table border="1">')
        parts.append('<tr><th>Period</th><th>Revenue</th><th>Net Income</th><th>EPS</th></tr>')
        for row in range(random.randint(5, 15)):
            year = 2024 - row
            parts.append(f'<tr><td>FY{year}</td><td>{random_number()}</td>'
                        f'<td>{random_number()}</td><td>${random.randint(1,99)}.{random.randint(10,99)}</td></tr>')
        parts.append('</table>')
    
    # XBRL-like inline tags
    parts.append('<div xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">')
    parts.append('<ix:nonFraction name="us-gaap:Revenues">1,234,567,890</ix:nonFraction>')
    parts.append('</div>')
    
    parts.append('</body></html>')
    return ''.join(parts)


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SEC Filing Parsing Performance Benchmarks')
    parser.add_argument('--url', help='SEC filing URL to benchmark')
    parser.add_argument('--file', type=Path, help='Local file to benchmark')
    parser.add_argument('--sample', choices=list(SAMPLE_FILINGS.keys()), help='Use sample filing')
    parser.add_argument('--all-samples', action='store_true', help='Run all sample filings')
    parser.add_argument('--dir', type=Path, help='Directory of files to benchmark')
    parser.add_argument('--synthetic', type=float, help='Generate synthetic filing of N MB')
    parser.add_argument('--local-sec', type=Path, default=Path(r"C:\sec_data\Archives\edgar\data"),
                       help='Path to local SEC data directory')
    
    args = parser.parse_args()
    
    # Check dependencies
    deps = []
    if not HAS_BS4:
        deps.append("beautifulsoup4")
    if not HAS_LXML:
        deps.append("lxml")
    if not HAS_HTML2TEXT:
        deps.append("html2text")
    if not HAS_HTTPX:
        deps.append("httpx")
    
    if deps:
        print(f"Missing optional dependencies: {', '.join(deps)}")
        print(f"Install with: pip install {' '.join(deps)}")
        if not HAS_BS4 and not HAS_LXML:
            print("At least one parser (bs4 or lxml) is required.")
            return
    
    if args.dir:
        # Multi-file benchmark
        files = list(args.dir.glob('*.htm')) + list(args.dir.glob('*.html')) + list(args.dir.glob('*.txt'))
        if files:
            run_multi_file_benchmark(files[:20])  # Limit to 20 files
        else:
            print(f"No HTML/text files found in {args.dir}")
        return
    
    if args.synthetic:
        # Generate synthetic filing
        print(f"\nGenerating synthetic {args.synthetic}MB filing...")
        content = generate_synthetic_filing(size_mb=args.synthetic)
        suite_name = f"Synthetic {args.synthetic}MB Filing"
        print(f"Generated {len(content)/1024/1024:.2f}MB of content")
        suite = run_parsing_benchmarks(content, suite_name)
        suite.print_summary()
        return
    
    # Check for local SEC files if no other input specified
    if not args.file and not args.url and not args.sample and not args.all_samples:
        local_sec = args.local_sec
        if local_sec.exists():
            # Find large files to benchmark
            print(f"\nSearching for SEC files in {local_sec}...")
            all_files = []
            for ext in ['*.txt', '*.htm', '*.html']:
                all_files.extend(local_sec.glob(f'**/{ext}'))
            
            if all_files:
                # Sort by size and pick a few varied sizes
                all_files.sort(key=lambda f: f.stat().st_size, reverse=True)
                
                # Get largest, medium, and smallest
                test_files = []
                if len(all_files) >= 1:
                    test_files.append(all_files[0])  # Largest
                if len(all_files) >= 10:
                    test_files.append(all_files[len(all_files)//2])  # Medium
                if len(all_files) >= 20:
                    test_files.append(all_files[-1])  # Smallest
                
                print(f"Found {len(all_files)} files. Testing {len(test_files)} representative files:\n")
                
                for fpath in test_files:
                    size_mb = fpath.stat().st_size / 1024 / 1024
                    print(f"\n{'#'*70}")
                    print(f"# {fpath.name} ({size_mb:.2f}MB)")
                    print(f"{'#'*70}")
                    
                    content = fpath.read_text(encoding='utf-8', errors='replace')
                    suite = run_parsing_benchmarks(content, f"File: {fpath.name}")
                    suite.print_summary()
                return
            else:
                print(f"No filing files found in {local_sec}")
        
        # Fallback to synthetic
        print("No input specified and no local SEC files found. Generating synthetic test...")
        content = generate_synthetic_filing(size_mb=5.0)
        suite = run_parsing_benchmarks(content, "Synthetic 5MB Filing")
        suite.print_summary()
        return
    
    if args.all_samples:
        # Run all sample filings
        for name, url in SAMPLE_FILINGS.items():
            print(f"\n{'#'*70}")
            print(f"# {name}: {url}")
            print(f"{'#'*70}")
            try:
                content = await fetch_sec_filing(url)
                suite = run_parsing_benchmarks(content, f"SEC Filing: {name}")
                suite.print_summary()
            except Exception as e:
                print(f"ERROR: {e}")
        return
    
    # Single file/URL benchmark
    if args.file:
        content = args.file.read_text(encoding='utf-8', errors='replace')
        suite_name = f"File: {args.file.name}"
    elif args.url:
        content = await fetch_sec_filing(args.url)
        suite_name = f"URL: {args.url.split('/')[-1]}"
    elif args.sample:
        url = SAMPLE_FILINGS[args.sample]
        content = await fetch_sec_filing(url)
        suite_name = f"Sample: {args.sample}"
    else:
        # Default: use a small test string
        print("No input specified. Use --url, --file, --sample, or --all-samples")
        print("\nAvailable samples:")
        for name, url in SAMPLE_FILINGS.items():
            print(f"  --sample {name}")
        return
    
    print(f"\nContent size: {len(content)/1024/1024:.2f} MB")
    print(f"Content length: {len(content):,} characters")
    
    suite = run_parsing_benchmarks(content, suite_name)
    suite.print_summary()
    
    # Print recommendations
    print("\n" + "="*70)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("="*70)
    print("""
1. **Use lxml over html.parser** - 2-5x faster parsing
2. **Stream large files** - Use iterparse for files >10MB to control memory
3. **Pre-compile regex patterns** - Store compiled patterns as class attributes
4. **Extract text early** - Convert to plain text before regex operations
5. **Lazy section parsing** - Parse sections on-demand, not upfront
6. **Chunk large submissions** - Process <DOCUMENT> sections independently
7. **Cache parsed results** - Store extracted text/sections by content hash
8. **Use xpath over find_all** - lxml xpath is faster for complex queries
9. **Limit header search** - Only search first 50KB for SEC headers
10. **Parallel table extraction** - Tables can be extracted independently
""")


if __name__ == '__main__':
    asyncio.run(main())
