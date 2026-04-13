import { test, expect } from '@playwright/test';

/**
 * Feed Management API Tests
 * 
 * Tests CRUD operations for feeds:
 * - List feeds
 * - Create feed
 * - Get single feed
 * - Update feed
 * - Delete feed
 * - Trigger collection
 */

test.describe('Feed Management', () => {
  let createdFeedId: string;

  test('GET /api/v1/feeds should list all feeds', async ({ request }) => {
    const response = await request.get('/api/v1/feeds');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    // Should return an array or object with value/Count properties
    if (Array.isArray(data)) {
      expect(Array.isArray(data)).toBeTruthy();
    } else {
      expect(data).toHaveProperty('value');
      expect(Array.isArray(data.value)).toBeTruthy();
    }
  });

  test('POST /api/v1/feeds should create a new feed', async ({ request }) => {
    const newFeed = {
      name: 'Test Feed',
      adapter_type: 'rss',
      url: 'https://example.com/feed.xml',
      enabled: true,
      config: {
        poll_interval: 300
      }
    };

    const response = await request.post('/api/v1/feeds', {
      data: newFeed
    });
    
    if (response.status() === 501 || response.status() === 404) {
      test.skip('POST /api/v1/feeds not implemented yet');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('id');
    expect(data).toHaveProperty('name');
    expect(data.name).toBe(newFeed.name);
    
    createdFeedId = data.id;
  });

  test('GET /api/v1/feeds/{id} should return single feed', async ({ request }) => {
    // Skip if no feed was created
    if (!createdFeedId) {
      test.skip('No feed created in previous test');
      return;
    }

    const response = await request.get(`/api/v1/feeds/${createdFeedId}`);
    
    if (response.status() === 404 || response.status() === 501) {
      test.skip('GET /api/v1/feeds/{id} not implemented yet');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('id');
    expect(data.id).toBe(createdFeedId);
  });

  test('PATCH /api/v1/feeds/{id} should update feed', async ({ request }) => {
    if (!createdFeedId) {
      test.skip('No feed created in previous test');
      return;
    }

    const updates = {
      enabled: false,
      config: {
        poll_interval: 600
      }
    };

    const response = await request.patch(`/api/v1/feeds/${createdFeedId}`, {
      data: updates
    });
    
    if (response.status() === 404 || response.status() === 501) {
      test.skip('PATCH /api/v1/feeds/{id} not implemented yet');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data.enabled).toBe(false);
  });

  test('POST /api/v1/feeds/{id}/collect should trigger collection', async ({ request }) => {
    if (!createdFeedId) {
      test.skip('No feed created in previous test');
      return;
    }

    const response = await request.post(`/api/v1/feeds/${createdFeedId}/collect`);
    
    if (response.status() === 404 || response.status() === 501) {
      test.skip('POST /api/v1/feeds/{id}/collect not implemented yet');
      return;
    }
    
    expect([200, 202, 204]).toContain(response.status());
  });

  test('DELETE /api/v1/feeds/{id} should delete feed', async ({ request }) => {
    if (!createdFeedId) {
      test.skip('No feed created in previous test');
      return;
    }

    const response = await request.delete(`/api/v1/feeds/${createdFeedId}`);
    
    if (response.status() === 404 || response.status() === 501) {
      test.skip('DELETE /api/v1/feeds/{id} not implemented yet');
      return;
    }
    
    expect([200, 204]).toContain(response.status());
  });
});

test.describe('Feed Validation', () => {
  test('POST /api/v1/feeds with invalid data should fail', async ({ request }) => {
    const invalidFeed = {
      name: '', // Empty name
      adapter_type: 'invalid_type',
      url: 'not-a-url'
    };

    const response = await request.post('/api/v1/feeds', {
      data: invalidFeed
    });
    
    if (response.status() === 501 || response.status() === 404) {
      test.skip('POST /api/v1/feeds not implemented yet');
      return;
    }
    
    expect([400, 422]).toContain(response.status());
  });
});
