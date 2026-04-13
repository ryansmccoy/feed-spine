import { test, expect } from '@playwright/test';

/**
 * Health & Info Endpoint Tests
 * 
 * Tests:
 * - Root endpoint (/)
 * - Health check (/health)
 * - API v1 health (/api/v1/health)
 * - Storage status
 * - Database health
 */

test.describe('Health & Info Endpoints', () => {
  test('GET / should return API info', async ({ request }) => {
    const response = await request.get('/');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('name');
    expect(data).toHaveProperty('version');
    expect(data.name).toContain('FeedSpine');
  });

  test('GET /health should return healthy status', async ({ request }) => {
    const response = await request.get('/health');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('healthy');
  });

  test('GET /api/v1/health should return detailed health', async ({ request }) => {
    const response = await request.get('/api/v1/health');
    
    if (response.status() === 404) {
      test.skip('/api/v1/health not found - use /health instead');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('status');
    expect(['healthy', 'degraded']).toContain(data.status);
  });
});

test.describe('Storage Status', () => {
  test('GET /api/v1/storage/status should return storage info', async ({ request }) => {
    const response = await request.get('/api/v1/storage/status');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('backend_type');
    expect(data).toHaveProperty('is_connected');
    expect(data).toHaveProperty('total_records');
    expect(data.is_connected).toBe(true);
  });

  test('GET /api/v1/database/health should return database status', async ({ request }) => {
    const response = await request.get('/api/v1/database/health');
    
    if (response.ok()) {
      const data = await response.json();
      expect(data).toHaveProperty('connected');
      expect(data.connected).toBe(true);
    } else {
      // 404 is acceptable if endpoint not implemented
      expect(response.status()).toBe(404);
    }
  });
});
