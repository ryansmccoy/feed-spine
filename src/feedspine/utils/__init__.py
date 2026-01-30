"""FeedSpine utilities.

Common utilities for retry logic, rate limiting, key generation, versioning, etc.
"""

from feedspine.utils.keys import (
    AutoKeyGenerator,
    CompositeKeyBuilder,
    UniqueConstraint,
    URLKeyExtractor,
    auto_key,
    generate_content_key,
    # Transforms
    KeyTransform,
    JsonPath,
    Split,
    RegexExtract,
    DatePart,
    Concat,
    Lower,
    Strip,
    Chain,
)
from feedspine.utils.retry import (
    RetryConfig,
    RetryExhausted,
    RetryResult,
    retry,
    with_retry,
)
from feedspine.utils.versioning import (
    VersionedRecord,
    VersionStore,
    MemoryVersionStore,
    ChangeType,
    PipelineVersion,
    VersionedPipeline,
    VersionDiff,
    diff_versions,
    get_version_history,
    content_hash,
)

__all__ = [
    # Key generation
    "AutoKeyGenerator",
    "CompositeKeyBuilder",
    "UniqueConstraint",
    "URLKeyExtractor",
    "auto_key",
    "generate_content_key",
    # Transforms
    "KeyTransform",
    "JsonPath",
    "Split",
    "RegexExtract",
    "DatePart",
    "Concat",
    "Lower",
    "Strip",
    "Chain",
    # Versioning
    "VersionedRecord",
    "VersionStore",
    "MemoryVersionStore",
    "ChangeType",
    "PipelineVersion",
    "VersionedPipeline",
    "VersionDiff",
    "diff_versions",
    "get_version_history",
    "content_hash",
    # Retry
    "RetryConfig",
    "RetryExhausted", 
    "RetryResult",
    "retry",
    "with_retry",
]
