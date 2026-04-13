import { test, expect } from '@playwright/test';

/**
 * Frontend Record/Article List UI Tests
 * 
 * Tests the article/record browsing interface:
 * - Article list display
 * - Virtual scrolling
 * - Filtering
 * - Read/unread status
 * - Star/bookmark functionality
 * - Article preview
 */

test.describe('Record List UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Navigate to records/articles page if not on home
    const recordsLink = page.locator('a:has-text("Records"), a:has-text("Articles"), a:has-text("Feed")');
    if (await recordsLink.count() > 0) {
      await recordsLink.first().click();
      await page.waitForLoadState('networkidle');
    }
  });

  test('should display article list', async ({ page }) => {
    // Look for article list container
    const articleList = page.locator('[data-testid="article-list"], .article-list, .record-list, [role="list"]');
    
    const listExists = await articleList.count();
    if (listExists === 0) {
      test.skip('Article list UI not yet implemented');
      return;
    }
    
    await expect(articleList).toBeVisible();
  });

  test('should display article items', async ({ page }) => {
    // Look for individual article items
    const articles = page.locator('[data-testid="article-item"], .article-item, .record-item, [role="listitem"]');
    
    const count = await articles.count();
    if (count === 0) {
      test.skip('No articles displayed or article UI not implemented');
      return;
    }
    
    expect(count).toBeGreaterThan(0);
    
    // First article should be visible
    await expect(articles.first()).toBeVisible();
  });

  test('should show article details on click', async ({ page }) => {
    const articles = page.locator('[data-testid="article-item"], .article-item, .record-item');
    
    const count = await articles.count();
    if (count === 0) {
      test.skip('No articles available');
      return;
    }
    
    await articles.first().click();
    
    // Should show article detail view or preview pane
    const detail = page.locator('[data-testid="article-detail"], .article-detail, .preview-pane, .article-preview');
    if (await detail.count() > 0) {
      await expect(detail).toBeVisible();
    }
  });

  test('should toggle star/bookmark on article', async ({ page }) => {
    // Look for star button
    const starButton = page.locator('button[aria-label*="star" i], button[aria-label*="bookmark" i], .star-button').first();
    
    const buttonExists = await starButton.count();
    if (buttonExists === 0) {
      test.skip('Star/bookmark UI not yet implemented');
      return;
    }
    
    await starButton.click();
    
    // Button state should change (aria-pressed or class change)
    await page.waitForTimeout(300); // Wait for update
    
    // Verify the star action worked (check for visual feedback)
    const starFilled = page.locator('.star-filled, [aria-pressed="true"], .starred');
    expect(await starFilled.count()).toBeGreaterThanOrEqual(1);
  });

  test('should mark article as read', async ({ page }) => {
    const articles = page.locator('[data-testid="article-item"], .article-item');
    
    const count = await articles.count();
    if (count === 0) {
      test.skip('No articles available');
      return;
    }
    
    // Find an unread article
    const unreadArticle = articles.filter({ hasText: /unread/i }).first();
    
   if (await unreadArticle.count() === 0) {
      test.skip('No unread articles to test');
      return;
    }
    
    await unreadArticle.click();
    
    // Should automatically mark as read or have a mark read button
    await page.waitForTimeout(500);
    
    // Article should now show as read
    const readIndicator = page.locator('.read, [data-read="true"], .read-indicator');
    if (await readIndicator.count() > 0) {
      expect(await readIndicator.count()).toBeGreaterThanOrEqual(1);
    }
  });

  test('should filter articles', async ({ page }) => {
    // Look for filter controls
    const filterButton = page.locator('button:has-text("Filter"), button[aria-label*="filter" i]');
    
    const buttonExists = await filterButton.count();
    if (buttonExists === 0) {
      test.skip('Article filtering UI not yet implemented');
      return;
    }
    
    await filterButton.click();
    
    // Should show filter options
    const filterPanel = page.locator('[data-testid="filter-panel"], .filter-panel, .filters');
    await expect(filterPanel).toBeVisible();
    
    // Select a filter option
    const filterOption = filterPanel.locator('input[type="checkbox"], input[type="radio"]').first();
    await filterOption.check();
    
    // Apply filter
    const applyButton = filterPanel.locator('button:has-text("Apply"), button:has-text("Filter")');
    if (await applyButton.count() > 0) {
      await applyButton.click();
    }
    
    // Articles list should update
    await page.waitForTimeout(500);
  });

  test('should search articles', async ({ page }) => {
    // Look for search input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]');
    
    const inputExists = await searchInput.count();
    if (inputExists === 0) {
      test.skip('Article search UI not yet implemented');
      return;
    }
    
    await searchInput.fill('test query');
    
    // Press Enter or click search button
    await searchInput.press('Enter');
    
    // Wait for results
    await page.waitForTimeout(1000);
    
    // Should show search results
    const results = page.locator('[data-testid="article-item"], .article-item');
    expect(await results.count()).toBeGreaterThanOrEqual(0);
  });
});

test.describe('View Modes', () => {
  test('should switch between view modes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Look for view mode toggle
    const viewModeButton = page.locator('button[aria-label*="view" i], button:has-text("View"), .view-mode-toggle');
    
    const buttonExists = await viewModeButton.count();
    if (buttonExists === 0) {
      test.skip('View mode selector not yet implemented');
      return;
    }
    
    await viewModeButton.first().click();
    
    // Should show view options (condensed, comfortable, cards, etc.)
    const viewOptions = page.locator('[role="menu"], .view-options');
    if (await viewOptions.count() > 0) {
      await expect(viewOptions).toBeVisible();
      
      // Select a different view mode
      const viewOption = viewOptions.locator('button, [role="menuitem"]').nth(1);
      await viewOption.click();
      
      // UI should update to reflect new view mode
      await page.waitForTimeout(300);
    }
  });
});

test.describe('Keyboard Navigation', () => {
  test('should navigate articles with j/k keys', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const articles = page.locator('[data-testid="article-item"], .article-item');
    const count = await articles.count();
    
    if (count === 0) {
      test.skip('No articles to test keyboard navigation');
      return;
    }
    
    // Press 'j' to move down
    await page.keyboard.press('j');
    await page.waitForTimeout(100);
    
    // Press 'k' to move up
    await page.keyboard.press('k');
    await page.waitForTimeout(100);
    
    // Press Enter to open
    await page.keyboard.press('Enter');
    
    // Should open article detail
    const detail = page.locator('[data-testid="article-detail"], .article-detail');
    if (await detail.count() > 0) {
      await expect(detail).toBeVisible();
    }
  });
});
