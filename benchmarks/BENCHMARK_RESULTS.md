# SEC Filing Parsing Performance Benchmark Results

## Executive Summary

The benchmark tests the **correct workflow** for parsing SEC complete submission files:
1. **Split** the SGML container into individual `<DOCUMENT>` sections
2. **Parse** each extracted document (HTML/HTM) individually
3. **Extract** text and detect sections

## Test Files

| File | Size | Documents | Primary Doc |
|------|------|-----------|-------------|
| Apple 10-K (2017) | 13.42 MB | 97 | 2.56 MB |
| Wells Fargo 10-K (2015) | 127.63 MB | 216 | 0.72 MB |

---

## Benchmark Results by Stage

### Stage 1: Document Splitting (SGML Container Processing)

This is the **critical first step** - parsing the complete submission to extract individual documents.

| Operation | 13MB File | 127MB File | Notes |
|-----------|-----------|------------|-------|
| **Full Split (with content)** | 878 MB/s | 1,129 MB/s | Extracts all document content |
| **Lazy Split (metadata only)** | 1,844 MB/s | 1,964 MB/s | Faster if you only need doc list |
| **Header Extraction** | 2,161 MB/s | 21,226 MB/s | Only scans first 50KB |
| **XBRL Detection** | 739 MB/s | 780 MB/s | Regex-based namespace scan |

**Key Finding:** Document splitting is **extremely fast** - not a bottleneck!
- 127MB file splits in ~0.1 seconds
- Throughput exceeds 1 GB/s

---

### Stage 2: HTML Document Parsing (Per-Document)

These benchmarks run on the **primary document** (the actual 10-K HTML file).

| Parser | 2.56MB Doc | 0.72MB Doc | Memory | Verdict |
|--------|------------|------------|--------|---------|
| **lxml direct** | 47 MB/s | 38 MB/s | 2.6 MB | ✅ **FASTEST** |
| **lxml text_content()** | 32 MB/s | 43 MB/s | 2.6 MB | ✅ Fast text extraction |
| **lxml iterparse** | 23 MB/s | 23 MB/s | 2.7 MB | ✅ Memory efficient |
| **Regex cleanup** | 20 MB/s | 26 MB/s | 5.1 MB | Good for simple strip |
| **lxml table extraction** | 8 MB/s | 8 MB/s | 2.6 MB | Moderate |
| **BeautifulSoup + lxml** | 1.7 MB/s | 1.9 MB/s | 27.5 MB | ⚠️ 20x slower |
| **BeautifulSoup + html.parser** | 0.62 MB/s | 0.92 MB/s | 30.6 MB | ❌ **SLOWEST** |
| **html2text** | 0.98 MB/s | 0.98 MB/s | 2.6 MB | ❌ Very slow |

**Key Findings:**
1. **lxml is 20-50x faster than BeautifulSoup** for parsing
2. **html.parser is 3x slower than lxml backend** even in BS4
3. **html2text is a major bottleneck** - avoid for bulk processing
4. **Memory usage**: lxml uses 10x less memory than BS4

---

### Stage 3: Content Analysis

| Operation | Speed | Notes |
|-----------|-------|-------|
| Section detection (regex) | 7-11 MB/s | Runs on extracted text (~300KB) |
| Full parse pipeline | 1.5-1.7 MB/s | BS4 parse + text + sections |
| Streaming parse | 16-17 MB/s | lxml iterparse with cleanup |

---

### Stage 4: Full Submission Workflow

End-to-end processing: header → split → parse primary → extract text → sections

| File Size | Total Time | Throughput |
|-----------|------------|------------|
| 13.42 MB | 1.85s | 7.25 MB/s |
| 127.63 MB | 0.56s | 228 MB/s |

The 127MB file is actually **faster** because the primary document (10-K) is smaller!

---

## Identified Bottlenecks (Ranked)

1. **❌ BeautifulSoup html.parser** - 0.62 MB/s (worst)
2. **❌ html2text conversion** - 0.98 MB/s
3. **⚠️ BeautifulSoup + lxml** - 1.7 MB/s
4. **⚠️ Table extraction (BS4)** - 1.5 MB/s

---

## Optimization Recommendations

### Immediate Wins

```python
# ❌ SLOW (1.7 MB/s)
soup = BeautifulSoup(html, 'lxml')
text = soup.get_text()

# ✅ FAST (32-47 MB/s) - 20x speedup!
tree = lxml.html.fromstring(html)
text = tree.text_content()
```

### Architecture Recommendations

1. **Use lxml directly** instead of BeautifulSoup wrapper
   - 20-50x performance improvement
   - 10x less memory usage

2. **Stream large documents** with iterparse
   ```python
   for event, elem in lxml.etree.iterparse(file, html=True):
       process(elem)
       elem.clear()  # Free memory immediately
   ```

3. **Lazy document extraction** - Don't extract content until needed
   ```python
   # Get metadata fast (1,964 MB/s)
   docs = bench_document_splitting_lazy(content)
   
   # Extract content only for documents you need
   doc_content = content[doc['start']:doc['end']]
   ```

4. **Replace html2text** with lxml.text_content() for plain text
   - 32x faster (0.98 → 32 MB/s)

5. **Pre-compile regex patterns** at module level
   ```python
   # Module level - compiled once
   SECTION_PATTERN = re.compile(r'(?i)(?:^|\n)\s*(PART\s+[IVX]+)')
   ```

6. **Parallel processing** - Documents can be parsed independently
   ```python
   from concurrent.futures import ProcessPoolExecutor
   with ProcessPoolExecutor() as executor:
       results = executor.map(parse_document, documents)
   ```

7. **Cache parsed results** by content hash for repeated access

---

## Memory Analysis

| Operation | Peak Memory | Notes |
|-----------|-------------|-------|
| Load 127MB file | 127.6 MB | Expected - full file in memory |
| Document split | +1 MB | Very efficient |
| BS4 parse 2.5MB doc | +27 MB | 10x document size! |
| lxml parse 2.5MB doc | +2.6 MB | 1x document size |

**Recommendation:** For memory-constrained environments, use lxml's iterparse to process documents without loading full DOM.

---

## Throughput Summary

| Task | Current | Optimized | Improvement |
|------|---------|-----------|-------------|
| Document splitting | 1,100 MB/s | - | Already fast |
| HTML parsing (BS4) | 1.7 MB/s | 47 MB/s (lxml) | **28x** |
| Text extraction | 1.6 MB/s | 32 MB/s (lxml) | **20x** |
| html2text | 1.0 MB/s | 32 MB/s (lxml) | **32x** |

---

## Conclusion

The **document splitting stage is NOT a bottleneck** - it processes at 1+ GB/s.

The **real bottlenecks are in per-document HTML parsing**:
- BeautifulSoup adds significant overhead
- html2text is very slow
- Using lxml directly provides 20-50x speedups

For bulk SEC filing processing, switching from BeautifulSoup to direct lxml usage could improve overall throughput by **10-20x** while reducing memory by **10x**.
