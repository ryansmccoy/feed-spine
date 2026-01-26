"""Core configuration and utilities."""

from feedspine.core.checkpoint import (
    Checkpoint,
    CheckpointManager,
    CheckpointStore,
    FileCheckpointStore,
    MemoryCheckpointStore,
)
from feedspine.core.feedspine import CollectionResult, FeedSpine
from feedspine.core.resources import RateLimiter, ResourcePool, Semaphore

__all__ = [
    # Orchestrator
    "CollectionResult",
    "FeedSpine",
    # Resources
    "RateLimiter",
    "ResourcePool",
    "Semaphore",
    # Checkpointing
    "Checkpoint",
    "CheckpointManager",
    "CheckpointStore",
    "FileCheckpointStore",
    "MemoryCheckpointStore",
]
