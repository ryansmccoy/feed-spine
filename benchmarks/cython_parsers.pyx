# cython: language_level=3
"""Cython-optimized parsing functions.

Compile with: cythonize -i cython_parsers.pyx
"""

import cython
from cpython.mem cimport PyMem_Malloc, PyMem_Free


@cython.boundscheck(False)
@cython.wraparound(False)
def parse_accession_cython(str acc):
    """Parse SEC accession number: 0000320193-24-000081
    
    Returns tuple(cik: str, year: int, sequence: int) or None
    """
    cdef int length = len(acc)
    cdef int i
    cdef char c
    
    # Fast length check
    if length != 20:
        return None
    
    # Check dashes at positions 10 and 13
    if acc[10] != '-' or acc[13] != '-':
        return None
    
    # Validate digits
    for i in range(10):
        c = ord(acc[i])
        if c < 48 or c > 57:  # '0' = 48, '9' = 57
            return None
    
    for i in range(11, 13):
        c = ord(acc[i])
        if c < 48 or c > 57:
            return None
    
    for i in range(14, 20):
        c = ord(acc[i])
        if c < 48 or c > 57:
            return None
    
    # Parse components
    cdef str cik = acc[:10]
    cdef int year = int(acc[11:13])
    cdef int seq = int(acc[14:20])
    
    return (cik, year, seq)


@cython.boundscheck(False)
@cython.wraparound(False)
def parse_accession_batch_cython(list accessions):
    """Parse multiple accession numbers efficiently."""
    cdef int n = len(accessions)
    cdef list results = [None] * n
    cdef int i
    cdef str acc
    
    for i in range(n):
        acc = accessions[i]
        results[i] = parse_accession_cython(acc)
    
    return results


@cython.boundscheck(False)
@cython.wraparound(False)
def find_document_boundaries_cython(bytes data):
    """Find SEC document boundaries in complete submission file.
    
    Searches for <DOCUMENT> and </DOCUMENT> tags.
    Returns list of (start, end) byte positions.
    """
    cdef bytes start_tag = b'<DOCUMENT>'
    cdef bytes end_tag = b'</DOCUMENT>'
    cdef int start_len = 10
    cdef int end_len = 11
    cdef int data_len = len(data)
    cdef int pos = 0
    cdef int doc_start = -1
    cdef int doc_end = -1
    cdef list boundaries = []
    
    while pos < data_len:
        # Find start tag
        doc_start = data.find(start_tag, pos)
        if doc_start == -1:
            break
        
        # Find end tag
        doc_end = data.find(end_tag, doc_start + start_len)
        if doc_end == -1:
            break
        
        # Include the end tag in the boundary
        boundaries.append((doc_start, doc_end + end_len))
        pos = doc_end + end_len
    
    return boundaries


@cython.boundscheck(False)
@cython.wraparound(False)  
def extract_tag_content_cython(bytes data, bytes tag_name):
    """Extract content between <TAG> and </TAG>.
    
    More efficient than regex for simple tag extraction.
    """
    cdef bytes start_tag = b'<' + tag_name + b'>'
    cdef bytes end_tag = b'</' + tag_name + b'>'
    cdef int start_len = len(start_tag)
    cdef int start_pos = data.find(start_tag)
    
    if start_pos == -1:
        return None
    
    cdef int content_start = start_pos + start_len
    cdef int end_pos = data.find(end_tag, content_start)
    
    if end_pos == -1:
        return None
    
    return data[content_start:end_pos]


@cython.boundscheck(False)
@cython.wraparound(False)
def count_lines_cython(bytes data):
    """Count lines in byte data (faster than split/len)."""
    cdef int count = 1
    cdef int i
    cdef int n = len(data)
    cdef const unsigned char[:] view = data
    
    for i in range(n):
        if view[i] == 10:  # '\n'
            count += 1
    
    return count


@cython.boundscheck(False)
@cython.wraparound(False)
def hash_content_batch_cython(list contents):
    """Hash multiple content strings using FNV-1a.
    
    FNV-1a is simpler/faster than MD5/SHA for non-crypto hashing.
    """
    cdef int n = len(contents)
    cdef list hashes = [0] * n
    cdef int i, j
    cdef str content
    cdef unsigned long long h
    cdef bytes data
    cdef const unsigned char[:] view
    
    # FNV-1a constants for 64-bit
    cdef unsigned long long FNV_OFFSET = 14695981039346656037
    cdef unsigned long long FNV_PRIME = 1099511628211
    
    for i in range(n):
        content = contents[i]
        data = content.encode('utf-8')
        view = data
        h = FNV_OFFSET
        
        for j in range(len(data)):
            h ^= view[j]
            h *= FNV_PRIME
            h &= 0xFFFFFFFFFFFFFFFF  # Keep 64-bit
        
        hashes[i] = h
    
    return hashes
