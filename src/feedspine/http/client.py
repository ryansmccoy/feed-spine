"""HTTP client with rate limiting and retry support.

Provides a robust async HTTP client for feed collection with:
- Automatic rate limiting
- Retry with exponential backoff
- Streaming downloads to files
- Connection pooling

Example:
    >>> from feedspine.http import HttpClient
    >>> 
    >>> async with HttpClient(rate_limit=10.0) as client:
    ...     # Simple GET
    ...     response = await client.get("https://example.com/api")
    ...     
    ...     # Download to file
    ...     await client.download("https://example.com/file.txt", "local.txt")
    ...     
    ...     # Stream lines
    ...     async for line in client.stream_lines("https://example.com/large.txt"):
    ...         process(line)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

from feedspine.http.rate_limiter import RateLimiter


class HttpClientError(Exception):
    """Base exception for HTTP client errors."""
    pass


class RateLimitError(HttpClientError):
    """Raised when rate limited by server."""
    
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class DownloadError(HttpClientError):
    """Raised when download fails."""
    
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to download {url}: {reason}")


class HttpClient:
    """Async HTTP client with rate limiting and retry support.
    
    Features:
    - Automatic rate limiting
    - Retry with exponential backoff
    - Streaming downloads to temporary files with atomic rename
    - Connection pooling with HTTP/2 support
    
    Example:
        >>> async with HttpClient(rate_limit=10.0) as client:
        ...     response = await client.get("/api/endpoint")
        ...     content = await client.download(url, dest_path)
    
    Attributes:
        rate_limit: Requests per second limit
        user_agent: User-Agent header value
        timeout: Default request timeout in seconds
        max_retries: Maximum retry attempts
    """
    
    def __init__(
        self,
        base_url: str = "",
        rate_limit: float = 10.0,
        user_agent: str = "FeedSpine/1.0",
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ):
        """Initialize HTTP client.
        
        Args:
            base_url: Base URL for relative requests
            rate_limit: Maximum requests per second
            user_agent: User-Agent header
            timeout: Default request timeout
            max_retries: Maximum retry attempts on failure
            headers: Additional default headers
            
        Raises:
            ImportError: If httpx package is not installed
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "HttpClient requires the 'httpx' package. "
                "Install with: pip install httpx"
            )
        
        self._base_url = base_url
        self._rate_limiter = RateLimiter(rate_limit)
        self._user_agent = user_agent
        self._timeout = timeout
        self._max_retries = max_retries
        self._extra_headers = headers or {}
        self._client: httpx.AsyncClient | None = None
    
    @property
    def rate_limit(self) -> float:
        """Current rate limit (requests per second)."""
        return self._rate_limiter.rate
    
    @property
    def user_agent(self) -> str:
        """User-Agent header value."""
        return self._user_agent
    
    @property
    def timeout(self) -> float:
        """Default request timeout in seconds."""
        return self._timeout
    
    @property
    def max_retries(self) -> int:
        """Maximum retry attempts."""
        return self._max_retries
    
    @property
    def headers(self) -> dict[str, str]:
        """Default headers for requests."""
        return {
            "User-Agent": self._user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "*/*",
            **self._extra_headers,
        }
    
    async def _ensure_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            # Try HTTP/2 if h2 is available
            try:
                import h2  # noqa: F401
                use_http2 = True
            except ImportError:
                use_http2 = False
            
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self.headers,
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
                http2=use_http2,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "HttpClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def _request(
        self,
        method: str,
        url: str,
        *,
        retry: bool = True,
        **kwargs: Any,
    ) -> "httpx.Response":
        """Make a rate-limited request with retries.
        
        Args:
            method: HTTP method
            url: URL (relative to base_url or absolute)
            retry: Whether to retry on failure
            **kwargs: Additional arguments for httpx
            
        Returns:
            HTTP response
            
        Raises:
            RateLimitError: If rate limited by server
            HttpClientError: For other HTTP errors
        """
        client = await self._ensure_client()
        
        max_retries = self._max_retries if retry else 0
        last_error: Exception | None = None
        
        for attempt in range(max_retries + 1):
            await self._rate_limiter.acquire()
            
            try:
                response = await client.request(method, url, **kwargs)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "10"))
                    if attempt < max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(retry_after)
                
                # Raise for bad status codes
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (500, 502, 503, 504):
                    # Server error - retry with backoff
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                raise HttpClientError(f"HTTP {e.response.status_code}: {e}") from e
                
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise HttpClientError(f"Request timeout: {e}") from e
                
            except httpx.RequestError as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise HttpClientError(f"Request failed: {e}") from e
        
        raise HttpClientError(f"Max retries exceeded: {last_error}")
    
    async def get(self, url: str, **kwargs: Any) -> "httpx.Response":
        """Make a GET request.
        
        Args:
            url: URL (relative or absolute)
            **kwargs: Additional arguments for httpx
            
        Returns:
            HTTP response
        """
        return await self._request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs: Any) -> "httpx.Response":
        """Make a POST request.
        
        Args:
            url: URL (relative or absolute)
            **kwargs: Additional arguments for httpx
            
        Returns:
            HTTP response
        """
        return await self._request("POST", url, **kwargs)
    
    async def get_text(self, url: str, **kwargs: Any) -> str:
        """Get text content from URL.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments
            
        Returns:
            Response text
        """
        response = await self.get(url, **kwargs)
        return response.text
    
    async def get_json(self, url: str, **kwargs: Any) -> Any:
        """Get JSON content from URL.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments
            
        Returns:
            Parsed JSON
        """
        response = await self.get(url, **kwargs)
        return response.json()
    
    async def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        """Get binary content from URL.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments
            
        Returns:
            Response bytes
        """
        response = await self.get(url, **kwargs)
        return response.content
    
    async def download(
        self,
        url: str,
        dest: Path | str,
        *,
        chunk_size: int = 8192,
    ) -> Path:
        """Download a file to local storage.
        
        Uses a temporary file to avoid partial downloads, then
        atomically renames to the destination path.
        
        Args:
            url: URL to download
            dest: Destination path
            chunk_size: Download chunk size
            
        Returns:
            Path to downloaded file
            
        Raises:
            DownloadError: If download fails
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Use temp file to avoid partial downloads
        temp_path = dest.with_suffix(dest.suffix + ".tmp")
        
        try:
            await self._rate_limiter.acquire()
            client = await self._ensure_client()
            
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                
                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size):
                        f.write(chunk)
            
            # Atomic move
            temp_path.replace(dest)
            return dest
            
        except Exception as e:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            raise DownloadError(url, str(e)) from e
    
    async def stream_lines(self, url: str) -> AsyncIterator[str]:
        """Stream text content line by line.
        
        Useful for processing large files without loading
        everything into memory.
        
        Args:
            url: URL to stream
            
        Yields:
            Lines of text
        """
        await self._rate_limiter.acquire()
        client = await self._ensure_client()
        
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                yield line


@asynccontextmanager
async def http_client(
    base_url: str = "",
    **kwargs: Any,
) -> AsyncIterator[HttpClient]:
    """Context manager for HTTP client.
    
    Example:
        >>> async with http_client(rate_limit=10.0) as client:
        ...     text = await client.get_text("/some/url")
    """
    client = HttpClient(base_url=base_url, **kwargs)
    try:
        async with client:
            yield client
    finally:
        await client.close()


__all__ = [
    "HttpClient",
    "HttpClientError",
    "RateLimitError",
    "DownloadError",
    "http_client",
]
