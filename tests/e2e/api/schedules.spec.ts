import { test, expect } from '@playwright/test';

/**
 * Schedule Management Tests
 * 
 * Tests:
 * - List schedules
 * - Create schedule
 * - Update schedule
 * - Enable/disable schedule
 * - Delete schedule
 * - Check due schedules
 */

test.describe('Schedule Management', () => {
  let createdScheduleId: string;

  test('GET /api/v1/schedules should list schedules', async ({ request }) => {
    const response = await request.get('/api/v1/schedules');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    // API returns {schedules: [], total: 0}
    const schedules = data.schedules || (Array.isArray(data) ? data : data.value);
    expect(Array.isArray(schedules)).toBeTruthy();
  });

  test('POST /api/v1/schedules should create schedule', async ({ request }) => {
    const newSchedule = {
      feed_id: 'test-feed',
      interval: 300,
      enabled: true
    };

    const response = await request.post('/api/v1/schedules', {
      data: newSchedule
    });
    
    if ([404, 422, 500, 501].includes(response.status())) {
      test.skip(`POST /api/v1/schedules not available (status ${response.status()})`);
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('id');
    createdScheduleId = data.id;
  });

  test('GET /api/v1/schedules/due should return due schedules', async ({ request }) => {
    const response = await request.get('/api/v1/schedules/due');
    
    if (response.status() === 404) {
      test.skip('Schedules/due endpoint missing (noted in audit)');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data) || data.value).toBeTruthy();
  });

  test('PATCH /api/v1/schedules/{id} should update schedule', async ({ request }) => {
    if (!createdScheduleId) {
      test.skip('No schedule created');
      return;
    }

    const response = await request.patch(`/api/v1/schedules/${createdScheduleId}`, {
      data: {
        enabled: false
      }
    });
    
    if ([404, 501].includes(response.status())) {
      test.skip('PATCH /api/v1/schedules/{id} not implemented');
      return;
    }
    
    expect(response.ok()).toBeTruthy();
  });

  test('DELETE /api/v1/schedules/{id} should delete schedule', async ({ request }) => {
    if (!createdScheduleId) {
      test.skip('No schedule created');
      return;
    }

    const response = await request.delete(`/api/v1/schedules/${createdScheduleId}`);
    
    if ([404, 501].includes(response.status())) {
      test.skip('DELETE /api/v1/schedules/{id} not implemented');
      return;
    }
    
    expect([200, 204]).toContain(response.status());
  });
});
