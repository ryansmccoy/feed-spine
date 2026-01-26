//! High-performance SEC filing parsers in Rust via PyO3
//!
//! Build with: maturin develop --release
//!
//! Operations that benefit from Rust:
//! - Accession number parsing (no GIL, SIMD-friendly)
//! - Document boundary detection (parallel search)
//! - Content hashing (parallel FNV-1a)
//! - Large file splitting (memory-mapped, parallel)

use pyo3::prelude::*;
use rayon::prelude::*;

/// Parse SEC accession number: 0000320193-24-000081
/// Returns (cik, year, sequence) or None
#[pyfunction]
fn parse_accession(acc: &str) -> Option<(String, u8, u32)> {
    let bytes = acc.as_bytes();
    
    // Fast length check
    if bytes.len() != 20 {
        return None;
    }
    
    // Check dashes
    if bytes[10] != b'-' || bytes[13] != b'-' {
        return None;
    }
    
    // Validate all digits in one pass
    for (i, &b) in bytes.iter().enumerate() {
        match i {
            0..=9 | 11..=12 | 14..=19 => {
                if !b.is_ascii_digit() {
                    return None;
                }
            }
            _ => {}
        }
    }
    
    // Parse components
    let cik = String::from_utf8_lossy(&bytes[0..10]).to_string();
    let year = (bytes[11] - b'0') * 10 + (bytes[12] - b'0');
    let seq = std::str::from_utf8(&bytes[14..20])
        .ok()?
        .parse::<u32>()
        .ok()?;
    
    Some((cik, year, seq))
}

/// Parse batch of accession numbers (parallel)
#[pyfunction]
fn parse_accession_batch(accessions: Vec<String>) -> Vec<Option<(String, u8, u32)>> {
    accessions
        .par_iter()
        .map(|acc| parse_accession(acc))
        .collect()
}

/// Find document boundaries in SEC complete submission
/// Returns Vec<(start, end)> byte positions
#[pyfunction]
fn find_document_boundaries(data: &[u8]) -> Vec<(usize, usize)> {
    const START_TAG: &[u8] = b"<DOCUMENT>";
    const END_TAG: &[u8] = b"</DOCUMENT>";
    
    let mut boundaries = Vec::new();
    let mut pos = 0;
    
    while pos < data.len() {
        // Find start tag
        if let Some(start_offset) = find_subsequence(&data[pos..], START_TAG) {
            let doc_start = pos + start_offset;
            
            // Find end tag after start
            let search_start = doc_start + START_TAG.len();
            if let Some(end_offset) = find_subsequence(&data[search_start..], END_TAG) {
                let doc_end = search_start + end_offset + END_TAG.len();
                boundaries.push((doc_start, doc_end));
                pos = doc_end;
            } else {
                break;
            }
        } else {
            break;
        }
    }
    
    boundaries
}

/// Find subsequence in byte slice (KMP would be faster for repeated patterns)
#[inline]
fn find_subsequence(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

/// Split complete submission into documents (parallel search for boundaries)
#[pyfunction]
fn split_documents(data: &[u8]) -> Vec<&[u8]> {
    let boundaries = find_document_boundaries(data);
    boundaries
        .iter()
        .map(|&(start, end)| &data[start..end])
        .collect()
}

/// FNV-1a hash for content fingerprinting (64-bit)
#[inline]
fn fnv1a_hash(data: &[u8]) -> u64 {
    const FNV_OFFSET: u64 = 14695981039346656037;
    const FNV_PRIME: u64 = 1099511628211;
    
    let mut hash = FNV_OFFSET;
    for &byte in data {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

/// Hash multiple content strings in parallel
#[pyfunction]
fn hash_content_batch(contents: Vec<String>) -> Vec<u64> {
    contents
        .par_iter()
        .map(|s| fnv1a_hash(s.as_bytes()))
        .collect()
}

/// Count lines in data (parallel)
#[pyfunction]
fn count_lines(data: &[u8]) -> usize {
    data.par_iter().filter(|&&b| b == b'\n').count() + 1
}

/// Extract content between <TAG> and </TAG>
#[pyfunction]
fn extract_tag_content<'py>(
    py: Python<'py>,
    data: &[u8],
    tag_name: &str,
) -> Option<&'py pyo3::types::PyBytes> {
    let start_tag = format!("<{}>", tag_name);
    let end_tag = format!("</{}>", tag_name);
    
    let start_pos = find_subsequence(data, start_tag.as_bytes())?;
    let content_start = start_pos + start_tag.len();
    
    let end_pos = find_subsequence(&data[content_start..], end_tag.as_bytes())?;
    let content = &data[content_start..content_start + end_pos];
    
    Some(pyo3::types::PyBytes::new(py, content))
}

/// Python module definition
#[pymodule]
fn sec_parsers(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_accession, m)?)?;
    m.add_function(wrap_pyfunction!(parse_accession_batch, m)?)?;
    m.add_function(wrap_pyfunction!(find_document_boundaries, m)?)?;
    m.add_function(wrap_pyfunction!(split_documents, m)?)?;
    m.add_function(wrap_pyfunction!(hash_content_batch, m)?)?;
    m.add_function(wrap_pyfunction!(count_lines, m)?)?;
    m.add_function(wrap_pyfunction!(extract_tag_content, m)?)?;
    Ok(())
}
