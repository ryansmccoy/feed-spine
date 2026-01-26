# FeedSpine Examples

Working examples demonstrating FeedSpine capabilities.

## Quick Start

```bash
# Install FeedSpine
pip install feedspine

# Run the quickstart example
python examples/01_quickstart.py
```

## Examples

| Example | Description |
|---------|-------------|
| [01_quickstart.py](01_quickstart.py) | Basic feed collection with deduplication |
| [02_multi_feed.py](02_multi_feed.py) | Collecting from multiple feeds |
| [03_duckdb_storage.py](03_duckdb_storage.py) | Persistent storage with DuckDB |
| [04_sec_edgar_feed.py](04_sec_edgar_feed.py) | SEC EDGAR filing monitoring |
| [05_entityspine_integration.py](05_entityspine_integration.py) | Integration with EntitySpine |

## Installation Options

```bash
# Core only
pip install feedspine

# With DuckDB (for example 03)
pip install feedspine[duckdb]

# For EntitySpine integration (example 05)
pip install entityspine
```

## Industry Use Cases

See the markdown files for detailed industry examples:

- [Financial Services](01_FINANCIAL_SERVICES_EXAMPLE.md) - SEC EDGAR monitoring
- [Media & News](02_MEDIA_NEWS_AGGREGATION_EXAMPLE.md) - News aggregation
- [E-Commerce](03_ECOMMERCE_PRICE_MONITORING_EXAMPLE.md) - Price monitoring
- [DevOps](04_DEVOPS_MONITORING_EXAMPLE.md) - Alert aggregation
- [Healthcare](05_HEALTHCARE_RESEARCH_EXAMPLE.md) - Research data
- [Social Media](06_SOCIAL_MEDIA_INTELLIGENCE_EXAMPLE.md) - Social monitoring

## Running Examples

Each example is self-contained and can be run directly:

```bash
cd feedspine

# Basic examples
python examples/01_quickstart.py
python examples/02_multi_feed.py

# Requires DuckDB
pip install feedspine[duckdb]
python examples/03_duckdb_storage.py

# SEC EDGAR monitoring
python examples/04_sec_edgar_feed.py

# EntitySpine integration
pip install entityspine
python examples/05_entityspine_integration.py
```
