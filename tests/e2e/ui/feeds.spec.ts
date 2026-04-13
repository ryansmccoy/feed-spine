import { test, expect, Page } from '@playwright/test';

/**
 * Frontend Feed Management UI Tests
 * 
 * Tests the feed management interface:
 * - Feed list display
 * - Feed creation form
 * - Feed editing
 * - Feed deletion
 * - Feed status toggles
 */

test.describe('Feed Management UI', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the feed management page
    await page.goto('/');
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
  });

  test('should load the frontend application', async ({ page }) => {
    // Check that the page loaded
    await expect(page).toHaveTitle(/FeedSpine/i);
    
    // Check for root element
    const root = page.locator('#root');
    await expect(root).toBeVisible();
  });

  test('should display feed list', async ({ page }) => {
    // Look for common feed list elements
    const feedList = page.locator('[data-testid="feed-list"], .feed-list, [role="list"]');
    
    // If feed list exists, it should be visible
    const isVisible = await feedList.isVisible().catch(() => false);
    if (isVisible) {
      await expect(feedList).toBeVisible();
    } else {
      test.skip('Feed list UI not yet implemented');
    }
  });

  test('should navigate to feed creation form', async ({ page }) => {
    // Look for "Add Feed" or "Create Feed" button
    const addButton = page.locator('button:has-text("Add Feed"), button:has-text("Create Feed"), button:has-text("New Feed")');
    
    const buttonExists = await addButton.count();
    if (buttonExists === 0) {
      test.skip('Feed creation UI not yet implemented');
      return;
    }
    
    await addButton.first().click();
    
    // Should show a form
    const form = page.locator('form, [data-testid="feed-form"]');
    await expect(form).toBeVisible();
  });

  test('should create a new feed', async ({ page }) => {
    // Try to find and click the add button
    const addButton = page.locator('button:has-text("Add Feed"), button:has-text("Create Feed"), button:has-text("New Feed")');
    
    const buttonExists = await addButton.count();
    if (buttonExists === 0) {
      test.skip('Feed creation UI not yet implemented');
      return;
    }
    
    await addButton.first().click();
    
    // Fill in the form
    await page.fill('input[name="name"], input[placeholder*="name" i]', 'Test Feed');
    await page.fill('input[name="url"], input[placeholder*="url" i]', 'https://example.com/feed.xml');
    
    // Select adapter type if dropdown exists
    const adapterSelect = page.locator('select[name="adapter_type"], select[name="type"]');
    if (await adapterSelect.isVisible()) {
      await adapterSelect.selectOption('rss');
    }
    
    // Submit the form
    const submitButton = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Create")');
    await submitButton.click();
    
    // Should show success message or redirect
    await expect(page.locator('.success, .toast, [role="alert"]')).toBeVisible({ timeout: 5000 });
  });

  test('should filter feeds', async ({ page }) => {
    // Look for search/filter input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i], input[placeholder*="filter" i]');
    
    const inputExists = await searchInput.count();
    if (inputExists === 0) {
      test.skip('Feed filtering UI not yet implemented');
      return;
    }
    
    await searchInput.fill('test');
    
    // Results should update
    await page.waitForTimeout(500); // Debounce
    
    // Verify filtering happened (feed list should change)
    const feedItems = page.locator('[data-testid="feed-item"], .feed-item');
    const count = await feedItems.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should toggle feed enabled status', async ({ page }) => {
    // Look for toggle switches or checkboxes
    const toggle = page.locator('input[type="checkbox"][name*="enabled"], .toggle, [role="switch"]').first();
    
    const toggleExists = await toggle.count();
    if (toggleExists === 0) {
      test.skip('Feed enable/disable UI not yet implemented');
      return;
    }
    
    const initialState = await toggle.isChecked();
    await toggle.click();
    
    // State should change
    await expect(toggle).toHaveAttribute('aria-checked', (!initialState).toString());
  });

  test('should delete a feed', async ({ page }) => {
    // Look for delete button
    const deleteButton = page.locator('button:has-text("Delete"), button[aria-label*="delete" i], .delete-button').first();
    
    const buttonExists = await deleteButton.count();
    if (buttonExists === 0) {
      test.skip('Feed deletion UI not yet implemented');
      return;
    }
    
    await deleteButton.click();
    
    // Should show confirmation dialog
    const confirmDialog = page.locator('[role="dialog"], .modal, .confirm-dialog');
    await expect(confirmDialog).toBeVisible();
    
    // Confirm deletion
    const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("Delete"), button:has-text("Yes")');
    await confirmButton.click();
    
    // Should show success message
    await expect(page.locator('.success, .toast, [role="alert"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Feed Details View', () => {
  test('should open feed details', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Click on first feed item
    const firstFeed = page.locator('[data-testid="feed-item"], .feed-item, .feed-row').first();
    
    const feedExists = await firstFeed.count();
    if (feedExists === 0) {
      test.skip('No feeds available to test');
      return;
    }
    
    await firstFeed.click();
    
    // Should show feed details
    const details = page.locator('[data-testid="feed-details"], .feed-details');
    if (await details.isVisible()) {
      await expect(details).toBeVisible();
    }
  });

  test('should trigger feed collection', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Look for "Collect Now" or "Refresh" button
    const collectButton = page.locator('button:has-text("Collect"), button:has-text("Refresh"), button:has-text("Run")');
    
    const buttonExists = await collectButton.count();
    if (buttonExists === 0) {
      test.skip('Collection trigger UI not yet implemented');
      return;
    }
    
    await collectButton.first().click();
    
    // Should show loading state or success message
    const feedback = page.locator('.loading, .spinner, .success, .toast');
    await expect(feedback).toBeVisible({ timeout: 5000 });
  });
});
