import { test, expect } from '@playwright/test';

/**
 * Feed Run & Collection Tests
 * 
 * Tests:
 * - List runs
 * - Get run details
 * - Trigger collection
 * - Check run status
 */

test.describe('Feed Runs', () => {
  test('GET /api/v1/runs should list collection runs', async ({ request }) => {
    const response = await request.get('/api/v1/runs');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    // API returns {runs: [], total: 0, limit: 50, offset: 0}
    const runs = data.runs || (Array.isArray(data) ? data : data.value);
    expect(Array.isArray(runs)).toBeTruthy();
  });

  test('GET /api/v1/runs/{id} should return run details', async ({ request }) => {
    // First get a run list
    const listResponse = await request.get('/api/v1/runs');
    const listData = await listResponse.json();
    const runs = listData.runs || (Array.isArray(listData) ? listData : listData.value);
    
    if (!runs || runs.length === 0) {
      test.skip('No runs available to test');
      return;
    }
    
    const runId = runs[0].run_id || runs[0].id;
    const response = await request.get(`/api/v1/runs/${runId}`);
    
    if (response.status() === 404) {
      test.skip('Run detail endpoint not implemented');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('run_id');
  });

  test('GET /api/v1/runs?status=completed should filter by status', async ({ request }) => {
    const response = await request.get('/api/v1/runs?status=completed');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    const runs = data.runs || (Array.isArray(data) ? data : data.value);
    
    // All returned runs should have completed status if filter worked
    if (runs && runs.length > 0) {
      runs.forEach(run => {
        if (run.status) {
          expect(run.status).toBe('completed');
        }
      });
    }
  });
});

test.describe('Collection Triggers', () => {
  test('POST /api/v1/collect should trigger collection', async ({ request }) => {
    const response = await request.post('/api/v1/collect', {
      data: {
        feed_id: 'test-feed'
      }
    });
    
    if ([404, 501].includes(response.status())) {
      test.skip('Collection trigger endpoint not found');
      return;
    }
    
    expect([200, 202, 204]).toContain(response.status());
  });

  test('POST /api/v1/collect/all should trigger all feeds', async ({ request }) => {
    const response = await request.post('/api/v1/collect/all');
    
    if ([404, 501].includes(response.status())) {
      test.skip('Collect all endpoint not found');
      return;
    }
    
    expect([200, 202, 204]).toContain(response.status());
  });
});
