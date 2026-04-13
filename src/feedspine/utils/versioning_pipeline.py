"""ML/LLM pipeline versioning support.

Extracted from :mod:`feedspine.utils.versioning` for single-responsibility.

Classes
-------
PipelineVersion
    Track which pipeline/model version produced output.
VersionedPipeline
    Helper for versioning ML/LLM pipeline outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from feedspine.utils.versioning import (
    ChangeType,
    VersionedRecord,
    VersionStore,
    content_hash,
)


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
            old_pipeline is None
            or old_pipeline.pipeline_version != self.pipeline_info.pipeline_version
            or old_pipeline.model_version != self.pipeline_info.model_version
        )

        content_changed = new_hash != latest.content_hash

        if not content_changed and not pipeline_changed:
            # No change
            return False, latest

        # Determine change type and reason
        if pipeline_changed and not content_changed:
            change_type = ChangeType.REPROCESSED
            reason = (
                change_reason
                or f"Reprocessed with {self.pipeline_info.pipeline_name} v{self.pipeline_info.pipeline_version}"
            )
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
            old_pipeline.pipeline_version != self.pipeline_info.pipeline_version
            or old_pipeline.model_version != self.pipeline_info.model_version
        )

    def get_stale_keys(self, keys: list[str]) -> list[str]:
        """Get keys that need reprocessing."""
        return [k for k in keys if self.needs_reprocess(k)]
