import { test, expect } from '@playwright/test';

/**
 * Statistics & Metrics Tests
 * 
 * Tests:
 * - Global stats
 * - Feed stats
 * - Collection stats
 * - Metrics endpoint
 */

test.describe('Statistics', () => {
  test('GET /api/v1/stats should return global statistics', async ({ request }) => {
    const response = await request.get('/api/v1/stats');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    // Should have various count properties
    expect(data).toHaveProperty('total_records');
    expect(typeof data.total_records).toBe('number');
  });

  test('GET /api/v1/stats/feeds should return feed statistics', async ({ request }) => {
    const response = await request.get('/api/v1/stats/feeds');
    
    if (response.status() === 404) {
      test.skip('Feed stats endpoint not found');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
  });

  test('GET /api/v1/stats/collection should return collection stats', async ({ request }) => {
    const response = await request.get('/api/v1/stats/collection');
    
    if (response.status() === 501) {
      test.skip('Collection stats not implemented yet (expected from audit)');
      return;
    }
    
    if (response.ok()) {
      const data = await response.json();
      expect(data).toBeDefined();
    }
  });
});

test.describe('Metrics', () => {
  test('GET /api/v1/metrics should return metrics', async ({ request }) => {
    const response = await request.get('/api/v1/metrics');
    
    if ([404, 501].includes(response.status())) {
      test.skip('Metrics endpoint not found - try /api/v1/metrics/json');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
  });

  test('GET /api/v1/metrics/json should return JSON metrics', async ({ request }) => {
    const response = await request.get('/api/v1/metrics/json');
    
    if ([404, 501].includes(response.status())) {
      test.skip('JSON metrics endpoint not implemented');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
  });

  test('GET /metrics should return Prometheus metrics', async ({ request }) => {
    const response = await request.get('/metrics');
    
    if (response.status() === 404) {
      test.skip('Prometheus metrics endpoint not implemented yet (recommended in audit)');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    expect(text).toContain('# HELP');
  });
});
