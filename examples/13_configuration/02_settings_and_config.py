#!/usr/bin/env python3
"""
Configuration Management — Settings, YAML Config & Storage Config
====================================================================

This example demonstrates FeedSpine's **configuration system** —
environment-based settings, YAML/TOML feed configs, and storage tuning.

What You'll Learn:
    1. `FeedSpineSettings` — env-based app configuration
    2. YAML-based feed configuration with env variable interpolation
    3. `StorageConfig` — database connection pool tuning
    4. Building retry and storage configs from settings
    5. Finding and loading config files automatically

Key Concepts:
    - FeedSpineSettings: Pydantic BaseSettings with FEEDSPINE_* prefix
    - FeedConfig: YAML/TOML-loaded feed definitions
    - StorageConfig: Storage backend tuning parameters
    - RetryConfig: Retry behavior (backoff delays, max attempts)

Usage:
    python examples/13_configuration/02_settings_and_config.py

Expected Output:
    Shows configuration loading, defaults, and derived configs.
"""

import os
import warnings

from feedspine.core.config import FeedSpineSettings
from feedspine.core.storage_config import StorageConfig

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


def main() -> None:
    # =========================================================================
    # STEP 1: Application Settings (Environment Variables)
    # =========================================================================
    print("=" * 60)
    print("STEP 1: Application Settings (FeedSpineSettings)")
    print("=" * 60)

    # Settings load from FEEDSPINE_* env vars with sensible defaults
    # Set some example env vars to demonstrate
    os.environ["FEEDSPINE_LOG_FORMAT"] = "text"
    os.environ["FEEDSPINE_STORAGE"] = "memory"
    os.environ["FEEDSPINE_DEFAULT_BATCH_SIZE"] = "200"
    os.environ["FEEDSPINE_MAX_RETRIES"] = "5"

    settings = FeedSpineSettings()

    print(f"\n  Server port:          {settings.port}")
    print(f"  Log format:           {settings.log_format}")
    print(f"  Storage backend:      {settings.storage}")
    print(f"  Default batch size:   {settings.default_batch_size}")
    print(f"  Request timeout:      {settings.request_timeout}s")
    print(f"  Adapter timeout:      {settings.adapter_timeout}s")
    print(f"  Rate limit delay:     {settings.rate_limit_delay}s")

    # =========================================================================
    # STEP 2: Retry Configuration (From Settings)
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 2: Retry Configuration (Derived)")
    print("=" * 60)

    retry = settings.get_retry_config()
    print(f"\n  Max attempts:    {retry.max_attempts}")
    print(f"  Base delay:      {retry.base_delay}s")
    print(f"  Max delay:       {retry.max_delay}s")

    # =========================================================================
    # STEP 3: Storage Configuration
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Storage Configuration (Pool Tuning)")
    print("=" * 60)

    storage_config = StorageConfig.from_settings(settings)
    print(f"\n  Pool size:       {storage_config.pool_size}")
    print(f"  Max overflow:    {storage_config.max_overflow}")
    print(f"  Pool timeout:    {storage_config.pool_timeout}s")
    print(f"  Pool recycle:    {storage_config.pool_recycle}s")
    print(f"  Batch size:      {storage_config.batch_size}")

    # Custom storage config for high-throughput scenarios
    ht_config = StorageConfig(
        pool_size=20,
        max_overflow=30,
        pool_timeout=10,
        pool_recycle=900,
        batch_size=5000,
    )
    print("\n  High-throughput config:")
    print(f"    Pool size:     {ht_config.pool_size}")
    print(f"    Max overflow:  {ht_config.max_overflow}")
    print(f"    Batch size:    {ht_config.batch_size}")

    # =========================================================================
    # STEP 4: Auth Settings
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Auth Configuration")
    print("=" * 60)

    print(f"\n  Auth required:   {settings.require_auth}")
    print(f"  API key set:     {settings.api_key is not None}")
    print("""
  To enable API authentication, set:
    FEEDSPINE_REQUIRE_AUTH=true
    FEEDSPINE_API_KEY=your-secret-key
    """)

    # =========================================================================
    # STEP 5: YAML Feed Configuration Pattern
    # =========================================================================
    print("=" * 60)
    print("STEP 5: YAML Feed Configuration")
    print("=" * 60)
    print("""
  FeedSpine supports configuration-driven feed registration:

  # feeds.yaml
  storage:
    type: sqlite
    connection: feeds.db

  feeds:
    - name: sec-press-releases
      type: rss
      url: https://www.sec.gov/news/pressreleases.rss
      enabled: true

    - name: polygon-api
      type: json
      url: https://api.polygon.io/v2/reference/financials
      headers:
        Authorization: Bearer ${POLYGON_API_KEY}
      items_path: results
      timeout: 60

  Usage:
    from feedspine.core.feed_config import load_config, create_adapters_from_config

    config = load_config("feeds.yaml")
    adapters = create_adapters_from_config(config)
    """)

    # Cleanup demo env vars
    for key in [
        "FEEDSPINE_LOG_FORMAT",
        "FEEDSPINE_STORAGE",
        "FEEDSPINE_DEFAULT_BATCH_SIZE",
        "FEEDSPINE_MAX_RETRIES",
    ]:
        os.environ.pop(key, None)


if __name__ == "__main__":
    main()
