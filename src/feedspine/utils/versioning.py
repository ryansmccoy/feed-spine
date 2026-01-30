"""Version control for FeedSpine records.

Track changes to documents, files, or any data over time. Useful for:
- Document versioning (SEC filings that get amended)
- ML pipeline outputs (embeddings, model predictions)
- LLM outputs (generated content, extractions)
- Audit trails (what changed and when)

Key Concepts:
- VersionedRecord: A record with version tracking
- VersionStore: Storage abstraction for versions  
- ChangeDetector: Detect if content has changed
- VersionQuery: Query historical versions

Example:
    >>> from feedspine.utils.versioning import VersionedRecord, MemoryVersionStore
    >>> 
    >>> store = MemoryVersionStore()
    >>> 
    >>> # First version
    >>> v1 = VersionedRecord.create(
    ...     key="doc:12345",
    ...     content={"title": "Draft", "body": "Initial content"},
    ...     source="editor",
    ... )
    >>> store.save(v1)
    >>> 
    >>> # Update creates new version
    >>> v2 = v1.new_version(
    ...     content={"title": "Final", "body": "Updated content"},
    ...     change_reason="Finalized document",
    ... )
    >>> store.save(v2)
    >>> 
    >>> # Query versions
    >>> all_versions = store.get_versions("doc:12345")
    >>> latest = store.get_latest("doc:12345")
    >>> at_time = store.get_at_time("doc:12345", some_datetime)
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Protocol
from enum import Enum


class ChangeType(Enum):
    """Type of change between versions."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REPROCESSED = "reprocessed"  # Same content, new processing (e.g., new model)


def content_hash(content: Any) -> str:
    """Generate hash of content for change detection."""
    if isinstance(content, bytes):
        data = content
    elif isinstance(content, str):
        data = content.encode("utf-8")
    else:
        # JSON serialize for dicts/lists
        data = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    
    return hashlib.sha256(data).hexdigest()[:16]


@dataclass
class VersionedRecord:
    """A record with version tracking.
    
    Attributes:
        key: Unique identifier for the record (natural key)
        version: Version number (1, 2, 3, ...)
        content: The actual data/content
        content_hash: Hash of content for change detection
        created_at: When this version was created
        source: Where this version came from
        change_type: Type of change (created, updated, etc.)
        change_reason: Why this version was created
        parent_version: Previous version number (None for v1)
        metadata: Additional metadata (model version, pipeline run, etc.)
    """
    key: str
    version: int
    content: Any
    content_hash: str
    created_at: datetime
    source: str
    change_type: ChangeType
    change_reason: str | None = None
    parent_version: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(
        cls,
        key: str,
        content: Any,
        source: str,
        metadata: dict[str, Any] | None = None,
        change_reason: str | None = None,
    ) -> VersionedRecord:
        """Create the first version of a record."""
        return cls(
            key=key,
            version=1,
            content=content,
            content_hash=content_hash(content),
            created_at=datetime.now(),
            source=source,
            change_type=ChangeType.CREATED,
            change_reason=change_reason or "Initial version",
            parent_version=None,
            metadata=metadata or {},
        )
    
    def new_version(
        self,
        content: Any,
        source: str | None = None,
        change_reason: str | None = None,
        change_type: ChangeType | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VersionedRecord:
        """Create a new version from this record.
        
        Automatically detects if content actually changed.
        """
        new_hash = content_hash(content)
        content_changed = new_hash != self.content_hash
        
        # Determine change type
        if change_type:
            ct = change_type
        elif not content_changed:
            ct = ChangeType.REPROCESSED
        else:
            ct = ChangeType.UPDATED
        
        # Merge metadata
        merged_metadata = {**self.metadata}
        if metadata:
            merged_metadata.update(metadata)
        
        return VersionedRecord(
            key=self.key,
            version=self.version + 1,
            content=content,
            content_hash=new_hash,
            created_at=datetime.now(),
            source=source or self.source,
            change_type=ct,
            change_reason=change_reason,
            parent_version=self.version,
            metadata=merged_metadata,
        )
    
    def mark_deleted(self, reason: str | None = None) -> VersionedRecord:
        """Create a deletion marker version."""
        return VersionedRecord(
            key=self.key,
            version=self.version + 1,
            content=None,
            content_hash="",
            created_at=datetime.now(),
            source=self.source,
            change_type=ChangeType.DELETED,
            change_reason=reason or "Deleted",
            parent_version=self.version,
            metadata=self.metadata,
        )
    
    @property
    def is_deleted(self) -> bool:
        """Check if this version represents a deletion."""
        return self.change_type == ChangeType.DELETED
    
    @property
    def version_id(self) -> str:
        """Unique ID for this specific version."""
        return f"{self.key}@v{self.version}"
    
    def __repr__(self) -> str:
        return f"VersionedRecord({self.key!r}, v{self.version}, {self.change_type.value})"


# =============================================================================
# Version Store Abstraction
# =============================================================================

class VersionStore(ABC):
    """Abstract base for version storage backends."""
    
    @abstractmethod
    def save(self, record: VersionedRecord) -> None:
        """Save a versioned record."""
        ...
    
    @abstractmethod
    def get_latest(self, key: str) -> VersionedRecord | None:
        """Get the latest version of a record."""
        ...
    
    @abstractmethod
    def get_version(self, key: str, version: int) -> VersionedRecord | None:
        """Get a specific version of a record."""
        ...
    
    @abstractmethod
    def get_versions(self, key: str) -> list[VersionedRecord]:
        """Get all versions of a record, oldest first."""
        ...
    
    @abstractmethod
    def get_at_time(self, key: str, at: datetime) -> VersionedRecord | None:
        """Get the version that was current at a specific time."""
        ...
    
    def save_if_changed(self, record: VersionedRecord) -> tuple[bool, VersionedRecord]:
        """Save only if content has changed from latest version.
        
        Returns:
            Tuple of (was_saved, record) - record may be existing if no change
        """
        latest = self.get_latest(record.key)
        
        if latest is None:
            # First version
            self.save(record)
            return True, record
        
        if latest.content_hash == record.content_hash:
            # No change
            return False, latest
        
        # Create new version
        new_record = latest.new_version(
            content=record.content,
            source=record.source,
            change_reason=record.change_reason,
            metadata=record.metadata,
        )
        self.save(new_record)
        return True, new_record


class MemoryVersionStore(VersionStore):
    """In-memory version store for testing/development."""
    
    def __init__(self):
        # key -> version -> record
        self._store: dict[str, dict[int, VersionedRecord]] = {}
    
    def save(self, record: VersionedRecord) -> None:
        if record.key not in self._store:
            self._store[record.key] = {}
        self._store[record.key][record.version] = record
    
    def get_latest(self, key: str) -> VersionedRecord | None:
        versions = self._store.get(key, {})
        if not versions:
            return None
        max_version = max(versions.keys())
        return versions[max_version]
    
    def get_version(self, key: str, version: int) -> VersionedRecord | None:
        return self._store.get(key, {}).get(version)
    
    def get_versions(self, key: str) -> list[VersionedRecord]:
        versions = self._store.get(key, {})
        return [versions[v] for v in sorted(versions.keys())]
    
    def get_at_time(self, key: str, at: datetime) -> VersionedRecord | None:
        versions = self.get_versions(key)
        result = None
        for v in versions:
            if v.created_at <= at:
                result = v
            else:
                break
        return result
    
    def keys(self) -> list[str]:
        """Get all keys in the store."""
        return list(self._store.keys())
    
    def stats(self) -> dict[str, Any]:
        """Get store statistics."""
        total_versions = sum(len(v) for v in self._store.values())
        return {
            "total_keys": len(self._store),
            "total_versions": total_versions,
            "avg_versions_per_key": total_versions / len(self._store) if self._store else 0,
        }


# =============================================================================
# ML/LLM Pipeline Support
# =============================================================================

@dataclass
class PipelineVersion:
    """Track which pipeline/model version produced output.
    
    Useful for ML/LLM pipelines where you need to know:
    - Which model version generated this output
    - What parameters were used
    - Whether to reprocess with a new model
    """
    pipeline_name: str
    pipeline_version: str
    model_name: str | None = None
    model_version: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    
    def to_metadata(self) -> dict[str, Any]:
        """Convert to metadata dict for VersionedRecord."""
        return {
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "parameters": self.parameters,
        }
    
    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> PipelineVersion | None:
        """Extract pipeline version from record metadata."""
        if "pipeline_name" not in metadata:
            return None
        return cls(
            pipeline_name=metadata["pipeline_name"],
            pipeline_version=metadata["pipeline_version"],
            model_name=metadata.get("model_name"),
            model_version=metadata.get("model_version"),
            parameters=metadata.get("parameters", {}),
        )


class VersionedPipeline:
    """Helper for versioning ML/LLM pipeline outputs.
    
    Example:
        >>> pipeline = VersionedPipeline(
        ...     store=store,
        ...     pipeline_name="embedding",
        ...     pipeline_version="1.2.0",
        ...     model_name="text-embedding-ada-002",
        ... )
        >>> 
        >>> # Process and version
        >>> for doc in documents:
        ...     embedding = model.embed(doc.text)
        ...     pipeline.save_output(
        ...         key=f"doc:{doc.id}:embedding",
        ...         content={"vector": embedding, "text": doc.text},
        ...     )
        >>> 
        >>> # Later: check if reprocessing needed
        >>> if pipeline.needs_reprocess("doc:123:embedding"):
        ...     # Model version changed, reprocess
        ...     ...
    """
    
    def __init__(
        self,
        store: VersionStore,
        pipeline_name: str,
        pipeline_version: str,
        model_name: str | None = None,
        model_version: str | None = None,
        parameters: dict[str, Any] | None = None,
    ):
        self.store = store
        self.pipeline_info = PipelineVersion(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            model_name=model_name,
            model_version=model_version,
            parameters=parameters or {},
        )
    
    def save_output(
        self,
        key: str,
        content: Any,
        change_reason: str | None = None,
    ) -> tuple[bool, VersionedRecord]:
        """Save pipeline output with version tracking.
        
        Returns (was_new_version, record).
        """
        latest = self.store.get_latest(key)
        
        if latest is None:
            # First version
            record = VersionedRecord.create(
                key=key,
                content=content,
                source=self.pipeline_info.pipeline_name,
                metadata=self.pipeline_info.to_metadata(),
                change_reason=change_reason or f"Processed by {self.pipeline_info.pipeline_name}",
            )
            self.store.save(record)
            return True, record
        
        # Check if content changed OR pipeline version changed
        new_hash = content_hash(content)
        old_pipeline = PipelineVersion.from_metadata(latest.metadata)
        
        pipeline_changed = (
            old_pipeline is None or
            old_pipeline.pipeline_version != self.pipeline_info.pipeline_version or
            old_pipeline.model_version != self.pipeline_info.model_version
        )
        
        content_changed = new_hash != latest.content_hash
        
        if not content_changed and not pipeline_changed:
            # No change
            return False, latest
        
        # Determine change type and reason
        if pipeline_changed and not content_changed:
            change_type = ChangeType.REPROCESSED
            reason = change_reason or f"Reprocessed with {self.pipeline_info.pipeline_name} v{self.pipeline_info.pipeline_version}"
        else:
            change_type = ChangeType.UPDATED
            reason = change_reason or "Content updated"
        
        new_record = latest.new_version(
            content=content,
            source=self.pipeline_info.pipeline_name,
            change_reason=reason,
            change_type=change_type,
            metadata=self.pipeline_info.to_metadata(),
        )
        self.store.save(new_record)
        return True, new_record
    
    def needs_reprocess(self, key: str) -> bool:
        """Check if a record needs reprocessing with current pipeline version."""
        latest = self.store.get_latest(key)
        if latest is None:
            return True  # Never processed
        
        old_pipeline = PipelineVersion.from_metadata(latest.metadata)
        if old_pipeline is None:
            return True  # No pipeline info
        
        # Check version mismatch
        return (
            old_pipeline.pipeline_version != self.pipeline_info.pipeline_version or
            old_pipeline.model_version != self.pipeline_info.model_version
        )
    
    def get_stale_keys(self, keys: list[str]) -> list[str]:
        """Get keys that need reprocessing."""
        return [k for k in keys if self.needs_reprocess(k)]


# =============================================================================
# Diff/Change Tracking
# =============================================================================

@dataclass
class VersionDiff:
    """Difference between two versions."""
    key: str
    from_version: int
    to_version: int
    change_type: ChangeType
    content_changed: bool
    fields_changed: list[str] | None = None  # For dict content
    from_record: VersionedRecord | None = None
    to_record: VersionedRecord | None = None


def diff_versions(v1: VersionedRecord, v2: VersionedRecord) -> VersionDiff:
    """Compare two versions and return differences."""
    content_changed = v1.content_hash != v2.content_hash
    
    # Try to detect changed fields if both are dicts
    fields_changed = None
    if isinstance(v1.content, dict) and isinstance(v2.content, dict):
        fields_changed = []
        all_keys = set(v1.content.keys()) | set(v2.content.keys())
        for k in all_keys:
            if v1.content.get(k) != v2.content.get(k):
                fields_changed.append(k)
    
    return VersionDiff(
        key=v1.key,
        from_version=v1.version,
        to_version=v2.version,
        change_type=v2.change_type,
        content_changed=content_changed,
        fields_changed=fields_changed,
        from_record=v1,
        to_record=v2,
    )


def get_version_history(store: VersionStore, key: str) -> list[VersionDiff]:
    """Get full change history for a key."""
    versions = store.get_versions(key)
    if len(versions) < 2:
        return []
    
    history = []
    for i in range(1, len(versions)):
        history.append(diff_versions(versions[i-1], versions[i]))
    
    return history
