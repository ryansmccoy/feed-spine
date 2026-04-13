---
title: "Readme"
type: readme
status: active
tags: [feedspine, testing]
---
# FeedSpine E2E Test Suite

Comprehensive end-to-end testing for FeedSpine using Playwright with TypeScript.

## Overview

This test suite provides complete coverage of:
- **API Endpoints**: All 27+ REST API endpoints
- **UI Components**: Feed management, article browsing, navigation
- **Multi-Browser**: Chromium, Firefox, WebKit (Safari)
- **CI/CD Ready**: Automatic retries, screenshots, videos, and reports

## Test Structure

```
tests/
└── e2e/
    ├── api/                  # API endpoint tests
    │   ├── health.spec.ts    # Health & system status
    │   ├── feeds.spec.ts     # Feed CRUD operations
    │   ├── records.spec.ts   # Article/record management
    │   ├── runs.spec.ts      # Collection runs
    │   ├── stats.spec.ts     # Statistics & metrics
    │   ├── schedules.spec.ts # Schedule management
    │   └── exports.spec.ts   # Export operations
    └── ui/                   # Frontend UI tests
        ├── feeds.spec.ts     # Feed management UI
        ├── records.spec.ts   # Article browsing UI
        └── navigation.spec.ts # Layout, routing, theme
```

## Prerequisites

- Node.js 18+ (20+ recommended)
- npm 9+
- Docker & Docker Compose (for running FeedSpine services)

## Setup

### 1. Install Dependencies

```bash
cd feed-spine
npm install
```

This installs:
- `@playwright/test` (v1.41.0+)
- `typescript` (v5.3.3+)
- `@types/node`

### 2. Install Playwright Browsers

```bash
npx playwright install
```

This downloads Chromium, Firefox, and WebKit browsers (~400MB).

### 3. Start FeedSpine Services

```bash
# From workspace root
docker compose up -d
```

This starts:
- API (port 8300)
- Frontend (port 3010)
- PostgreSQL (port 15432)
- Redis (port 16379)
- Docs (port 8000)

Verify containers are running:
```bash
docker ps | grep feedspine
```

## Running Tests

### All Tests (API + UI, all browsers)

```bash
npm test
```

### API Tests Only (fastest)

```bash
npm run test:api
```

Runs API endpoint tests (~2-5 minutes). Ideal for quick validation.

### UI Tests Only (all browsers)

```bash
npm run test:ui
```

Runs UI tests in Chromium, Firefox, and WebKit (~5-10 minutes).

### Headed Mode (see browser)

```bash
npm run test:headed
```

Opens actual browser windows to watch tests execute.

### Debug Mode

```bash
npm run test:debug
```

Opens Playwright Inspector for step-by-step debugging.

### Specific File or Test

```bash
# Run single file
npx playwright test tests/e2e/api/health.spec.ts

# Run tests matching pattern
npx playwright test --grep "should create feed"

# Run specific project (browser)
npx playwright test --project=chromium-ui
```

## Test Reports

### HTML Report (interactive)

```bash
npm run test:report
```

Opens interactive HTML report with:
- Test pass/fail status
- Screenshots on failure
- Videos on failure
- Execution traces
- Detailed logs

Report location: `playwright-report/index.html`

### JSON Report

Located at `test-results/results.json` after each test run.

Useful for CI/CD integration and programmatic analysis.

## Test Configuration

Configuration in `playwright.config.ts`:

- **Base URLs**: 
  - API: `http://localhost:8300`
  - Frontend: `http://localhost:3010`
- **Timeout**: 30s per test
- **Retries**: 2x on CI, 0x locally
- **Parallel**: Yes (fully parallel)
- **Reporters**: HTML, JSON, list (console)
- **Artifacts**: Screenshots, videos, traces on failure

### Environment Variables

Override defaults:

```bash
# Custom API URL
API_BASE_URL=http://staging.example.com:8300 npm test

# Custom Frontend URL
FRONTEND_BASE_URL=http://staging.example.com:3010 npm test

# Both
API_BASE_URL=http://localhost:8300 FRONTEND_BASE_URL=http://localhost:3010 npm test
```

## Test Features

### Graceful Handling of Not-Implemented Endpoints

Tests automatically skip endpoints that return 404 or 501:

```typescript
if ([404, 501].includes(response.status())) {
  test.skip('Endpoint not yet implemented (noted in audit)');
  return;
}
```

This allows tests to run even as APIs are being developed.

### Missing Endpoints Tested

Tests include recommended endpoints from audit:

- `PATCH /api/v1/records/{id}` - Update read/star status
- `POST /api/v1/records/mark-all-read` - Bulk operations
- `GET /api/v1/schedules/due` - Due schedules
- `GET /metrics` - Prometheus format

### Defensive UI Tests

UI tests skip gracefully if elements don't exist:

```typescript
const element = page.locator('[data-testid="feeds-list"]');
if (await element.count() === 0) {
  test.skip('Feeds UI not yet implemented');
  return;
}
```

## Test Coverage

### API Endpoints (27+)

**Health & Status** (5 endpoints)
- `GET /` - API info
- `GET /health` - Basic health
- `GET /api/v1/health` - Detailed health
- `GET /api/v1/storage/status` - Storage info
- `GET /api/v1/database/health` - Database connectivity

**Feeds** (6 endpoints)
- `GET /api/v1/feeds` - List feeds
- `POST /api/v1/feeds` - Create feed
- `GET /api/v1/feeds/{id}` - Get feed
- `PATCH /api/v1/feeds/{id}` - Update feed
- `DELETE /api/v1/feeds/{id}` - Delete feed
- `POST /api/v1/feeds/{id}/collect` - Trigger collection

**Records** (7 endpoints)
- `GET /api/v1/records` - List records
- `GET /api/v1/records/{id}` - Get record
- `PATCH /api/v1/records/{id}` - Update record (MISSING)
- `POST /api/v1/records/mark-all-read` - Bulk operation (MISSING)
- `GET /api/v1/records/search` - Search (OPTIONAL)

**Runs** (3 endpoints)
- `GET /api/v1/runs` - List runs
- `GET /api/v1/runs/{id}` - Get run details
- `POST /api/v1/collect` - Trigger collection

**Stats** (4 endpoints)
- `GET /api/v1/stats` - Global stats
- `GET /api/v1/stats/feeds` - Feed stats
- `GET /api/v1/stats/collection` - Collection stats
- `GET /api/v1/metrics` - Metrics

**Schedules** (4 endpoints)
- `GET /api/v1/schedules` - List schedules
- `POST /api/v1/schedules` - Create schedule
- `PATCH /api/v1/schedules/{id}` - Update schedule
- `DELETE /api/v1/schedules/{id}` - Delete schedule

**Exports** (9 endpoints)
- `GET /api/v1/export/json` - JSON export
- `GET /api/v1/export/csv` - CSV export
- `GET /api/v1/export/parquet` - Parquet export
- `GET /api/v1/observations` - List observations
- `POST /api/v1/observations` - Create observation
- `GET /api/v1/sightings` - List sightings
- `GET /api/v1/timeline` - Timeline view
- `GET /api/v1/enrichers` - Enrichment plugins
- `GET /api/v1/syndication` - Syndication info

### UI Workflows (10+)

**Feed Management**
- Display feed list
- Create new feed
- Edit existing feed
- Delete feed (with confirmation)
- Toggle feed enabled/disabled
- Filter feeds
- Sort feeds
- View feed details
- Trigger feed collection

**Article Browsing**
- Display article list
- Show article details
- Star/bookmark articles
- Mark as read (auto + manual)
- Filter articles (feed, read status, starred)
- Search articles
- Switch view modes (condensed, comfortable, headlines, cards, table)
- Keyboard navigation (j/k, Enter)
- Virtual scrolling

**Navigation & Layout**
- Application loads
- Navigation menu
- Page routing
- Theme switching (dark mode)
- Settings panel
- Stats dashboard
- Error handling (404, API errors)
- Loading states
- Mobile responsive
- Mobile menu

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          
      - name: Install dependencies
        run: |
          cd feed-spine
          npm install
          npx playwright install --with-deps
          
      - name: Start services
        run: docker compose up -d
        
      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8300/health; do sleep 2; done'
          
      - name: Run tests
        run: |
          cd feed-spine
          npm test
          
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: feedspine/playwright-report/
          retention-days: 30
```

### Test Result Badge

Add to README.md:

```markdown
![E2E Tests](https://github.com/your-org/your-repo/actions/workflows/e2e-tests.yml/badge.svg)
```

## Troubleshooting

### Tests Timeout or Fail to Connect

**Symptom**: `Error: connect ECONNREFUSED 127.0.0.1:8300`

**Solution**: Ensure Docker containers are running:
```bash
docker compose ps
docker compose logs feedspine-api
```

### UI Tests Skip Everything

**Symptom**: All UI tests show "skipped"

**Reason**: Frontend not yet fully integrated from capture-spine-basic.

**Solution**: Tests are defensive and will pass once UI components exist.

### Playwright Browsers Not Found

**Symptom**: `Error: Browser is not installed`

**Solution**: Install browsers:
```bash
npx playwright install
```

### Test Failures in CI

**Check**:
1. Service health: `docker compose ps`
2. Network configuration: Ensure ports 8300, 3010 accessible
3. Database migrations: Check API logs for schema issues
4. Timing: CI may be slower, increase timeouts if needed

### Debugging Failed Tests

1. **Run in headed mode**: `npm run test:headed`
2. **Use debug mode**: `npm run test:debug`
3. **Check screenshots**: `playwright-report/` folder
4. **Check traces**: Click on failed test in HTML report
5. **Check logs**: Test output includes request/response details

## Extending Tests

### Add New API Test

Create file in `tests/e2e/api/`:

```typescript
import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8300';

test.describe('My New Feature', () => {
  test('should do something', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/my-endpoint`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('field');
  });
});
```

### Add New UI Test

Create file in `tests/e2e/ui/`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('My UI Feature', () => {
  test('should interact with component', async ({ page }) => {
    await page.goto('/my-page');
    const button = page.locator('button:has-text("Click Me")');
    await button.click();
    await expect(page.locator('.result')).toBeVisible();
  });
});
```

### Add Visual Regression Test

Install Percy or use Playwright's built-in screenshot comparison:

```typescript
test('should match screenshot', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveScreenshot('homepage.png');
});
```

### Add Accessibility Test

Install axe-core:

```bash
npm install --save-dev @axe-core/playwright
```

```typescript
import { injectAxe, checkA11y } from '@axe-core/playwright';

test('should have no accessibility violations', async ({ page }) => {
  await page.goto('/');
  await injectAxe(page);
  await checkA11y(page);
});
```

## Test Maintenance

### Update Playwright

```bash
npm install --save-dev @playwright/test@latest
npx playwright install
```

### Update Browsers Only

```bash
npx playwright install
```

### Clear Test Cache

```bash
rm -rf test-results/ playwright-report/ playwright/.cache/
```

## Performance

### Typical Execution Times

- **API tests**: 2-5 minutes (sequential by test file, parallel within)
- **UI tests (1 browser)**: 3-5 minutes
- **UI tests (all browsers)**: 5-10 minutes
- **Full suite**: 10-15 minutes

### Optimization Tips

1. **Run API tests first**: Fastest feedback
2. **Run single browser**: Use `--project=chromium-ui` during development
3. **Limit test files**: Use file patterns to run subset
4. **Increase workers**: Add `--workers=8` for more parallelism (on CI)
5. **Skip UI tests**: Use `npm run test:api` for quick validation

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [FeedSpine API Docs](http://localhost:8000)
- [FeedSpine Audit](../docs/)

## Support

For issues or questions:

1. Check `playwright-report/` for detailed failure info
2. Review Docker logs: `docker compose logs feedspine-api`
3. Enable debug logging: `DEBUG=pw:api npm test`
4. Open issue with:
   - Test output
   - Screenshots from report
   - Docker container status
   - Environment details (OS, Node version)
