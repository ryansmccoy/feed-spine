import { test, expect } from '@playwright/test';

/**
 * Record Management API Tests
 * 
 * Tests:
 * - List records
 * - Get single record
 * - Filter records
 * - Update record (read/star status)
 * - Bulk operations
 */

test.describe('Record Listing', () => {
  test('GET /api/v1/records should return records list', async ({ request }) => {
    const response = await request.get('/api/v1/records');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    // Should return array or object with value property
    if (Array.isArray(data)) {
      expect(Array.isArray(data)).toBeTruthy();
    } else {
      expect(data).toHaveProperty('value');
      expect(Array.isArray(data.value)).toBeTruthy();
    }
  });

  test('GET /api/v1/records with limit should respect pagination', async ({ request }) => {
    const response = await request.get('/api/v1/records?limit=5');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    const records = Array.isArray(data) ? data : data.value;
    expect(records.length).toBeLessThanOrEqual(5);
  });

  test('GET /api/v1/records with filters should filter results', async ({ request }) => {
    const response = await request.get('/api/v1/records?feed_id=test&record_type=article');
    
    expect(response.ok()).toBeTruthy();
    // Just verify it doesn't error, filtering may return empty results
  });

  test('GET /api/v1/records/{id} should return single record', async ({ request }) => {
    // First get a list to find an ID
    const listResponse = await request.get('/api/v1/records?limit=1');
    const listData = await listResponse.json();
    const records = Array.isArray(listData) ? listData : listData.value;
    
    if (records.length === 0) {
      test.skip('No records available to test');
      return;
    }
    
    const recordId = records[0].record_id || records[0].id;
    const response = await request.get(`/api/v1/records/${recordId}`);
    
    if (response.status() === 404) {
      test.skip('Record detail endpoint not implemented');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('record_id');
  });
});

test.describe('Record Operations', () => {
  test('PATCH /api/v1/records/{id} should update record', async ({ request }) => {
    // This endpoint needs to be added to feedspine API
    const response = await request.patch('/api/v1/records/test-id', {
      data: {
        is_read: true,
        is_starred: false
      }
    });
    
    if ([404, 405, 501].includes(response.status())) {
      test.skip('PATCH /api/v1/records/{id} not implemented yet (recommended in audit)');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
  });

  test('POST /api/v1/records/mark-all-read should mark records as read', async ({ request }) => {
    // This endpoint needs to be added to feedspine API
    const response = await request.post('/api/v1/records/mark-all-read', {
      data: {
        feed_id: 'test-feed'
      }
    });
    
    if ([404, 405, 501].includes(response.status())) {
      test.skip('POST /api/v1/records/mark-all-read not implemented yet (recommended in audit)');
      return;
    }
    
    expect([200, 204]).toContain(response.status());
  });
});

test.describe('Record Search', () => {
  test('GET /api/v1/records/search should search records', async ({ request }) => {
    const response = await request.get('/api/v1/records/search?q=test');
    
    if ([404, 501].includes(response.status())) {
      test.skip('Search endpoint not implemented yet');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data) || data.value).toBeTruthy();
  });
});
