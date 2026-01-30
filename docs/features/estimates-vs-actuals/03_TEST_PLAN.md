# Test Plan: Estimates vs Actuals

> **Comprehensive testing strategy for the comparison engine.**

---

## Testing Philosophy

1. **Unit tests** - Test individual methods in isolation
2. **Integration tests** - Test with real storage backend
3. **Property tests** - Verify invariants hold for generated data
4. **Scenario tests** - Test realistic earnings season workflows
5. **Edge case tests** - Handle missing data, timing edge cases

---

## Test Data Strategy

### Fixtures

```python
# tests/fixtures/estimates_actuals.py

import pytest
from datetime import datetime, date
from decimal import Decimal

@pytest.fixture
def sample_estimates():
    """Pre-announcement estimates from multiple sources."""
    return [
        # FactSet consensus for AAPL Q4 2024
        Observation(
            entity_id="aapl",
            metric=MetricSpec(code="eps", scope=EstimateScope.CONSENSUS),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.10"),
            as_of=datetime(2024, 10, 28),  # 3 days before report
            source=SourceKey(vendor="factset", feed="consensus"),
        ),
        # Bloomberg consensus (slightly different)
        Observation(
            entity_id="aapl",
            metric=MetricSpec(code="eps", scope=EstimateScope.CONSENSUS),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.12"),
            as_of=datetime(2024, 10, 28),
            source=SourceKey(vendor="bloomberg", feed="consensus"),
        ),
        # Post-announcement estimate (should be excluded)
        Observation(
            entity_id="aapl",
            metric=MetricSpec(code="eps", scope=EstimateScope.CONSENSUS),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.20"),  # Revised up after beat
            as_of=datetime(2024, 11, 5),  # AFTER the actual
            source=SourceKey(vendor="factset", feed="consensus"),
        ),
    ]

@pytest.fixture
def sample_actuals():
    """Reported actuals from SEC and company."""
    return [
        # Preliminary from earnings call
        Observation(
            entity_id="aapl",
            metric=MetricSpec(code="eps", scope=EstimateScope.REPORTED),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.18"),
            as_of=datetime(2024, 10, 31, 17, 0),  # 5 PM ET
            source=SourceKey(vendor="company", feed="earnings_release"),
        ),
        # Audited from 10-Q (supersedes preliminary)
        Observation(
            entity_id="aapl",
            metric=MetricSpec(code="eps", scope=EstimateScope.REPORTED),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.19"),  # Slight revision
            as_of=datetime(2024, 11, 15),
            source=SourceKey(vendor="sec", feed="10q_xbrl"),
            supersedes="preliminary_obs_id",
        ),
    ]

@pytest.fixture
def company_no_coverage():
    """Small company with actual but no analyst coverage."""
    return Observation(
        entity_id="smallcap123",
        metric=MetricSpec(code="eps", scope=EstimateScope.REPORTED),
        period=FiscalPeriod(year=2024, quarter=4),
        value=Decimal("0.50"),
        as_of=datetime(2024, 11, 1),
        source=SourceKey(vendor="sec", feed="10q_xbrl"),
    )
```

---

## Unit Tests

### 1. ComparisonResult Tests

```python
# tests/analysis/test_comparison_result.py

class TestComparisonResult:
    
    def test_beat_calculation(self):
        """Actual > estimate is a beat."""
        result = ComparisonResult(
            entity_id="aapl",
            metric_code="eps",
            period_key="2024:Q4",
            estimate=mock_estimate(2.10),
            actual=mock_actual(2.18),
        )
        assert result.beat is True
        assert result.direction == "BEAT"
    
    def test_miss_calculation(self):
        """Actual < estimate is a miss."""
        result = ComparisonResult(
            entity_id="aapl",
            metric_code="eps", 
            period_key="2024:Q4",
            estimate=mock_estimate(2.20),
            actual=mock_actual(2.10),
        )
        assert result.beat is False
        assert result.direction == "MISS"
    
    def test_exact_match_is_not_beat(self):
        """Tolerance is zero - exact match is not a beat."""
        result = ComparisonResult(
            entity_id="aapl",
            metric_code="eps",
            period_key="2024:Q4",
            estimate=mock_estimate(2.10),
            actual=mock_actual(2.10),
        )
        assert result.beat is False  # Not strictly greater
        assert result.direction == "INLINE"
    
    def test_no_estimate_direction(self):
        """Missing estimate has special direction."""
        result = ComparisonResult(
            entity_id="smallcap",
            metric_code="eps",
            period_key="2024:Q4",
            estimate=None,
            actual=mock_actual(0.50),
        )
        assert result.beat is None
        assert result.surprise_pct is None
        assert result.direction == "NO_ESTIMATE"
    
    def test_surprise_percentage_calculation(self):
        """Surprise = (actual - estimate) / |estimate|."""
        result = ComparisonResult(
            entity_id="aapl",
            metric_code="eps",
            period_key="2024:Q4",
            estimate=mock_estimate(2.00),
            actual=mock_actual(2.10),
        )
        assert result.surprise_pct == pytest.approx(0.05, rel=1e-6)  # +5%
    
    def test_surprise_with_negative_estimate(self):
        """Handle negative estimate (loss expected)."""
        result = ComparisonResult(
            entity_id="lossco",
            metric_code="eps",
            period_key="2024:Q4",
            estimate=mock_estimate(-0.50),  # Expected loss
            actual=mock_actual(-0.40),       # Smaller loss = beat
        )
        assert result.beat is True  # -0.40 > -0.50
        assert result.surprise_pct == pytest.approx(0.20, rel=1e-6)  # 20% better
```

### 2. Estimate Resolution Tests

```python
# tests/analysis/test_estimate_resolution.py

class TestEstimateResolution:
    
    async def test_pre_announcement_finds_latest_before_actual(self, storage, sample_data):
        """'pre_announcement' selects estimate just before actual."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            estimate_as_of="pre_announcement",
        )
        
        # Should pick Oct 28 estimate, not Nov 5 (post-announcement)
        assert result.estimate.as_of == datetime(2024, 10, 28)
        assert result.estimate.value == Decimal("2.10")
    
    async def test_explicit_as_of_timestamp(self, storage, sample_data):
        """Explicit timestamp finds estimate as of that date."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            estimate_as_of=datetime(2024, 10, 15),  # Earlier date
        )
        
        # Should find whatever estimate was known on Oct 15
        assert result.estimate.as_of <= datetime(2024, 10, 15)
    
    async def test_source_filter(self, storage, sample_data):
        """Source filter selects specific vendor."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            estimate_source="bloomberg",
        )
        
        assert result.estimate.source.vendor == "bloomberg"
        assert result.estimate.value == Decimal("2.12")
    
    async def test_no_estimate_returns_none(self, storage, company_no_coverage):
        """Company without analyst coverage has None estimate."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="smallcap123",
            metric_code="eps",
            period="2024:Q4",
        )
        
        assert result.estimate is None
        assert result.actual is not None
        assert result.direction == "NO_ESTIMATE"
```

### 3. Actual Resolution Tests

```python
# tests/analysis/test_actual_resolution.py

class TestActualResolution:
    
    async def test_authoritative_prefers_sec(self, storage, sample_data):
        """Authoritative actual prefers SEC over company release."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            actual_source=None,  # Authoritative (default)
        )
        
        # SEC 10-Q should be preferred over earnings release
        assert result.actual.source.vendor == "sec"
    
    async def test_specific_source_override(self, storage, sample_data):
        """Can explicitly request company-reported actual."""
        comparator = EstimateActualComparison(storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            actual_source="company",
        )
        
        assert result.actual.source.vendor == "company"
        assert result.actual.value == Decimal("2.18")  # Preliminary
```

---

## Integration Tests

### 4. Full Comparison Workflow

```python
# tests/integration/test_comparison_workflow.py

class TestComparisonWorkflow:
    
    @pytest.fixture
    async def loaded_storage(self, postgres_storage):
        """Storage with full test dataset."""
        # Load estimates
        await postgres_storage.store_many(ESTIMATE_FIXTURES)
        # Load actuals
        await postgres_storage.store_many(ACTUAL_FIXTURES)
        return postgres_storage
    
    async def test_single_company_comparison(self, loaded_storage):
        """Full single-company comparison flow."""
        comparator = EstimateActualComparison(loaded_storage)
        
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
        )
        
        assert result.entity_id == "aapl"
        assert result.estimate is not None
        assert result.actual is not None
        assert result.beat is True
        assert 0.03 < result.surprise_pct < 0.05
    
    async def test_batch_comparison(self, loaded_storage):
        """Batch comparison for all companies in period."""
        comparator = EstimateActualComparison(loaded_storage)
        
        results = []
        async for r in comparator.compare_all(
            period="2024:Q4",
            metric_code="eps",
        ):
            results.append(r)
        
        assert len(results) > 0
        # All results have actuals
        assert all(r.actual is not None for r in results)
        # Some may not have estimates
        with_estimates = [r for r in results if r.estimate is not None]
        assert len(with_estimates) > 0
```

### 5. Real-Time Detection Tests

```python
# tests/integration/test_realtime.py

class TestRealTimeDetection:
    
    async def test_recent_actuals(self, loaded_storage):
        """Find actuals in time window."""
        comparator = EstimateActualComparison(loaded_storage)
        
        # Insert a "just now" actual
        recent_actual = Observation(
            entity_id="msft",
            metric=MetricSpec(code="eps", scope=EstimateScope.REPORTED),
            period=FiscalPeriod(year=2024, quarter=4),
            value=Decimal("2.95"),
            as_of=datetime.utcnow() - timedelta(minutes=5),
            source=SourceKey(vendor="company", feed="earnings_release"),
        )
        await loaded_storage.store(recent_actual)
        
        # Query last 10 minutes
        recent = await comparator.recent_actuals(
            since=datetime.utcnow() - timedelta(minutes=10),
        )
        
        assert len(recent) >= 1
        assert any(r.entity_id == "msft" for r in recent)
    
    async def test_watch_transitions_detects_new_actual(self, loaded_storage):
        """Streaming detection finds new actuals."""
        comparator = EstimateActualComparison(loaded_storage)
        
        # Start watching in background
        events = []
        async def collect_events():
            async for event in comparator.watch_transitions(
                poll_interval_seconds=1,
                max_events=1,  # Stop after first event
            ):
                events.append(event)
        
        watch_task = asyncio.create_task(collect_events())
        
        # Simulate new actual arriving
        await asyncio.sleep(0.5)
        new_actual = create_test_actual("googl", "2024:Q4", Decimal("1.89"))
        await loaded_storage.store(new_actual)
        
        # Wait for detection
        await asyncio.wait_for(watch_task, timeout=5.0)
        
        assert len(events) == 1
        assert events[0].entity_id == "googl"
```

---

## Scenario Tests

### 6. Earnings Season Scenarios

```python
# tests/scenarios/test_earnings_season.py

class TestEarningsSeason:
    """
    Realistic earnings season scenarios.
    """
    
    async def test_dashboard_summary(self, loaded_storage):
        """Generate full earnings season dashboard."""
        comparator = EstimateActualComparison(loaded_storage)
        
        results = [r async for r in comparator.compare_all(
            period="2024:Q4",
            metric_code="eps",
        )]
        
        beats = [r for r in results if r.beat is True]
        misses = [r for r in results if r.beat is False]
        no_coverage = [r for r in results if r.estimate is None]
        
        # Verify reasonable distribution
        total = len(results)
        assert total > 10
        assert len(beats) / total > 0.4  # At least 40% beat
        assert len(misses) / total > 0.2  # At least 20% miss
    
    async def test_biggest_surprises(self, loaded_storage):
        """Find biggest positive and negative surprises."""
        comparator = EstimateActualComparison(loaded_storage)
        
        results = [r async for r in comparator.compare_all(
            period="2024:Q4",
            metric_code="eps",
        ) if r.surprise_pct is not None]
        
        by_surprise = sorted(results, key=lambda r: r.surprise_pct, reverse=True)
        
        biggest_beat = by_surprise[0]
        biggest_miss = by_surprise[-1]
        
        assert biggest_beat.surprise_pct > 0
        assert biggest_miss.surprise_pct < 0
    
    async def test_sector_breakdown(self, loaded_storage, entity_storage):
        """Break down beats/misses by sector."""
        comparator = EstimateActualComparison(loaded_storage)
        
        sector_stats = defaultdict(lambda: {"beat": 0, "miss": 0})
        
        async for r in comparator.compare_all(period="2024:Q4", metric_code="eps"):
            if r.beat is None:
                continue
            entity = await entity_storage.get(r.entity_id)
            sector = entity.sector or "Unknown"
            if r.beat:
                sector_stats[sector]["beat"] += 1
            else:
                sector_stats[sector]["miss"] += 1
        
        # Verify we got sector data
        assert len(sector_stats) > 1
```

---

## Edge Case Tests

### 7. Edge Cases

```python
# tests/analysis/test_edge_cases.py

class TestEdgeCases:
    
    async def test_zero_estimate(self):
        """Handle zero estimate (breakeven expected)."""
        result = await comparator.compare(
            entity_id="breakeven_co",
            metric_code="eps",
            period="2024:Q4",
        )
        # Zero estimate means any positive is infinite % surprise
        # Should handle gracefully
        assert result.surprise_pct is not None or result.direction == "INLINE"
    
    async def test_estimate_and_actual_same_timestamp(self):
        """Edge case: estimate and actual at exact same time."""
        # This shouldn't happen but might with bad data
        result = await comparator.compare(...)
        # Should still work - estimate as_of == actual as_of
        assert result is not None
    
    async def test_multiple_actuals_same_period(self):
        """Multiple actuals (preliminary + audited) for same period."""
        result = await comparator.compare(
            entity_id="aapl",
            metric_code="eps",
            period="2024:Q4",
            actual_source=None,  # Authoritative
        )
        # Should return the authoritative (audited) one
        assert result.actual.source.vendor == "sec"
    
    async def test_future_period(self):
        """Requesting comparison for future period."""
        with pytest.raises(NoActualError):
            await comparator.compare(
                entity_id="aapl",
                metric_code="eps",
                period="2099:Q4",  # Future
            )
    
    async def test_currency_mismatch(self):
        """Estimate in USD, actual in EUR."""
        # Should auto-convert
        result = await comparator.compare(
            entity_id="euro_company",
            metric_code="eps",
            period="2024:Q4",
        )
        # Values should be comparable (both converted to same currency)
        assert result.surprise_pct is not None
```

---

## Test Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| `ComparisonResult` | 100% |
| `EstimateActualComparison.compare()` | 95% |
| `EstimateActualComparison.compare_all()` | 90% |
| `EstimateActualComparison.recent_actuals()` | 90% |
| `EstimateActualComparison.watch_transitions()` | 85% |
| Edge cases | 100% |

---

## API Contract Tests (Phase 6)

### Request/Response Validation

```python
# tests/api/test_contracts.py

class TestAPIContracts:
    
    def test_compare_request_validation(self):
        """CompareRequest validates required fields."""
        # Valid
        req = CompareRequest(entity_id="AAPL", period="2024:Q4")
        assert req.metric_code == "eps"  # Default
        
        # Missing required field
        with pytest.raises(ValidationError):
            CompareRequest(period="2024:Q4")  # No entity_id
    
    def test_compare_response_serialization(self):
        """CompareResponse serializes to JSON correctly."""
        response = CompareResponse(
            entity_id="aapl",
            period="2024:Q4",
            metric_code="eps",
            identifiers={"ticker": "AAPL", "cik": "320193"},
            estimate=None,
            actual=ObservationResponse(...),
            surprise_pct=0.038,
            surprise_direction="BEAT",
        )
        
        json_data = response.model_dump_json()
        parsed = json.loads(json_data)
        
        assert parsed["surprise_direction"] == "BEAT"
        assert parsed["identifiers"]["ticker"] == "AAPL"
    
    def test_batch_response_summary_stats(self):
        """BatchCompareResponse calculates correct stats."""
        response = BatchCompareResponse(
            period="2024:Q4",
            metric_code="eps",
            total_companies=100,
            companies_with_estimates=80,
            beat_count=54,
            miss_count=26,
            beat_rate=0.675,
            results=[...],
        )
        
        assert response.beat_rate == 0.675
        assert response.beat_count + response.miss_count == 80
```

### Endpoint Tests

```python
# tests/api/test_endpoints.py

class TestAPIEndpoints:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_compare_endpoint(self, client, populated_storage):
        """POST /v1/compare returns comparison."""
        response = client.post("/v1/compare", json={
            "entity_id": "AAPL",
            "period": "2024:Q4",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == "aapl"
        assert data["surprise_direction"] in ["BEAT", "MISS", "INLINE", "NO_ESTIMATE"]
    
    def test_compare_entity_not_found(self, client):
        """Unknown entity returns 404."""
        response = client.post("/v1/compare", json={
            "entity_id": "NOTREAL",
            "period": "2024:Q4",
        })
        
        assert response.status_code == 404
        assert response.json()["code"] == "ENTITY_NOT_FOUND"
    
    def test_batch_compare_endpoint(self, client, populated_storage):
        """POST /v1/compare/batch returns summary."""
        response = client.post("/v1/compare/batch", json={
            "period": "2024:Q4",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "beat_rate" in data
        assert "results" in data
    
    def test_recent_actuals_endpoint(self, client, populated_storage):
        """GET /v1/recent returns time-filtered results."""
        response = client.get("/v1/recent", params={
            "since_minutes": 60,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
```

### WebSocket Tests

```python
# tests/api/test_websocket.py

class TestWebSocket:
    
    async def test_earnings_stream_connection(self):
        """WebSocket connects and receives messages."""
        async with websocket_connect("/v1/stream/earnings") as ws:
            # Simulate new actual arriving
            await simulate_new_actual("AAPL", "2024:Q4")
            
            message = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            
            assert message["type"] == "NEW_ACTUAL"
            assert message["entity_id"] == "aapl"
    
    async def test_stream_filters_by_criteria(self):
        """WebSocket respects filter criteria."""
        async with websocket_connect("/v1/stream/earnings?min_surprise=5") as ws:
            # Small surprise - should NOT trigger
            await simulate_new_actual("AAPL", surprise_pct=0.02)
            
            # Large surprise - SHOULD trigger
            await simulate_new_actual("NVDA", surprise_pct=0.10)
            
            message = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            assert message["entity_id"] == "nvda"  # Only large surprise
```

---

## Price Integration Tests (Phase 7)

```python
# tests/analysis/test_price_integration.py

class TestEarningsPriceAnalysis:
    
    async def test_earnings_price_reaction(self, obs_storage, price_storage):
        """Price reaction captures pre/post correctly."""
        analyzer = EarningsPriceAnalysis(obs_storage, price_storage)
        
        result = await analyzer.earnings_price_reaction(
            entity_id="aapl",
            period="2024:Q4",
            pre_days=5,
            post_days=5,
        )
        
        assert result.price_pre is not None
        assert result.price_post is not None
        assert result.price_change_pct is not None
        assert result.surprise_pct is not None
    
    async def test_pead_analysis(self, obs_storage, price_storage):
        """Post-earnings drift calculated correctly."""
        analyzer = EarningsPriceAnalysis(obs_storage, price_storage)
        
        pead = await analyzer.pead_analysis(
            period="2024:Q4",
            drift_days=[1, 5, 20],
        )
        
        # Beats should drift positive (typically)
        # Misses should drift negative (typically)
        assert "beats_1d" in pead
        assert "misses_1d" in pead
```

---

## Adjustment Tracking Tests (Phase 8)

```python
# tests/domain/test_adjustments.py

class TestAdjustmentChain:
    
    def test_total_calculation(self):
        """Chain calculates total adjustment."""
        chain = AdjustmentChain([
            Adjustment("RESTRUCTURING", Decimal("0.05")),
            Adjustment("LITIGATION", Decimal("0.02")),
            Adjustment("TAX_IMPACT", Decimal("-0.01")),
        ])
        
        assert chain.total == Decimal("0.06")
    
    def test_adjustment_lineage_query(self, storage):
        """Can query full GAAP → Operating chain."""
        gaap_eps = await storage.store(Observation(
            metric=MetricSpec(code="eps", basis=MetricBasis.GAAP),
            value=Decimal("2.10"),
        ))
        
        adjusted_eps = await storage.store(Observation(
            metric=MetricSpec(code="eps", basis=MetricBasis.ADJUSTED),
            value=Decimal("2.16"),
            derived_from=gaap_eps.id,
            adjustments=AdjustmentChain([
                Adjustment("RESTRUCTURING", Decimal("0.05")),
                Adjustment("LITIGATION", Decimal("0.01")),
            ]),
        ))
        
        lineage = await storage.get_adjustment_lineage(adjusted_eps.id)
        
        assert lineage.origin.value == Decimal("2.10")
        assert lineage.final.value == Decimal("2.16")
        assert len(lineage.adjustments) == 2
```

---

## CI/CD Integration

```yaml
# .github/workflows/test.yml

jobs:
  test-estimates-actuals:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: pytest tests/analysis/ -v --cov=feedspine.analysis
      - name: Run integration tests
        run: pytest tests/integration/test_comparison*.py -v
      - name: Run scenario tests
        run: pytest tests/scenarios/ -v
```

---

*Test early, test often, test edge cases.* 🧪
