"""FeedSpine utilities.

Common utilities for retry logic, rate limiting, key generation, versioning, etc.
"""

from feedspine.utils.constraints import UniqueConstraint
from feedspine.utils.keys import (
    AutoKeyGenerator,
    CompositeKeyBuilder,
    URLKeyExtractor,
    auto_key,
    generate_content_key,
)
from feedspine.utils.retry import (
    RetryConfig,
    RetryExhausted,
    RetryResult,
    retry,
    with_retry,
)
from feedspine.utils.transforms import (
    Chain,
    ColumnSpec,
    Concat,
    DatePart,
    JsonPath,
    KeyTransform,
    Lower,
    RegexExtract,
    Split,
    Strip,
)
from feedspine.utils.versioning import (
    ChangeType,
    MemoryVersionStore,
    PipelineVersion,
    VersionDiff,
    VersionedPipeline,
    VersionedRecord,
    VersionStore,
    content_hash,
    diff_versions,
    get_version_history,
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
    "ColumnSpec",
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
