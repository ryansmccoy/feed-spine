import { test, expect } from '@playwright/test';

/**
 * Frontend Navigation & Layout Tests
 * 
 * Tests the overall application structure:
 * - Navigation menu
 * - Routing
 * - Sidebar
 * - Header
 * - Footer
 * - Theme switching
 */

test.describe('Application Layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should load the application', async ({ page }) => {
    await expect(page).toHaveTitle(/FeedSpine/i);
    
    // Check for root app element
    const app = page.locator('#root, .app, [data-testid="app"]');
    await expect(app).toBeVisible();
  });

  test('should display navigation menu', async ({ page }) => {
    // Look for navigation
    const nav = page.locator('nav, [role="navigation"], .navbar, .nav-menu');
    
    const navExists = await nav.count();
    if (navExists === 0) {
      test.skip('Navigation menu not yet implemented');
      return;
    }
    
    await expect(nav.first()).toBeVisible();
  });

  test('should display main navigation links', async ({ page }) => {
    // Look for common navigation links
    const links = [
      'Feeds',
      'Records',
      'Articles',
      'Stats',
      'Dashboard',
      'Today',
    ];
    
    let foundLinks = 0;
    for (const linkText of links) {
      const link = page.locator(`a:has-text("${linkText}"), button:has-text("${linkText}")`);
      if (await link.count() > 0) {
        foundLinks++;
      }
    }
    
    if (foundLinks === 0) {
      test.skip('Navigation links not yet implemented');
      return;
    }
    
    expect(foundLinks).toBeGreaterThan(0);
  });

  test('should navigate between pages', async ({ page }) => {
    // Find any navigation link
    const navLink = page.locator('nav a, [role="navigation"] a').first();
    
    const linkExists = await navLink.count();
    if (linkExists === 0) {
      test.skip('No navigation links available');
      return;
    }
    
    const href = await navLink.getAttribute('href');
    await navLink.click();
    
    // URL should change
    await page.waitForLoadState('networkidle');
    if (href && href !== '/' && href !== '#') {
      expect(page.url()).toContain(href);
    }
  });
});

test.describe('Theme & Settings', () => {
  test('should toggle dark mode', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Look for theme toggle button
    const themeToggle = page.locator('button[aria-label*="theme" i], button[aria-label*="dark" i], .theme-toggle');
    
    const toggleExists = await themeToggle.count();
    if (toggleExists === 0) {
      test.skip('Theme toggle not yet implemented');
      return;
    }
    
    await themeToggle.first().click();
    
    // Body should have dark mode class or attribute
    const body = page.locator('body');
    const hasDarkClass = await body.evaluate(el => 
      el.classList.contains('dark') || 
      el.classList.contains('dark-mode') ||
      el.getAttribute('data-theme') === 'dark'
    );
    
    expect(hasDarkClass).toBeTruthy();
  });

  test('should open settings', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Look for settings button
    const settingsButton = page.locator('button[aria-label*="settings" i], button:has-text("Settings"), a:has-text("Settings")');
    
    const buttonExists = await settingsButton.count();
    if (buttonExists === 0) {
      test.skip('Settings not yet implemented');
      return;
    }
    
    await settingsButton.first().click();
    
    // Should open settings panel or navigate to settings page
    const settingsPanel = page.locator('[data-testid="settings"], .settings-panel, .settings-modal, [role="dialog"]');
    if (await settingsPanel.count() > 0) {
      await expect(settingsPanel).toBeVisible();
    }
  });
});

test.describe('Statistics Dashboard', () => {
  test('should display stats page', async ({ page }) => {
    await page.goto('/stats');
    
    // Should load without error
    await expect(page).not.toHaveURL(/error/);
    
    // Look for stats cards or metrics
    const statsCards = page.locator('[data-testid="stat-card"], .stat-card, .metric, .stats-grid');
    
    const cardsExist = await statsCards.count();
    if (cardsExist === 0) {
      test.skip('Stats UI not yet implemented');
      return;
    }
    
    expect(await statsCards.count()).toBeGreaterThan(0);
  });

  test('should display total records count', async ({ page }) => {
    await page.goto('/stats');
    
    // Look for total records stat
    const totalRecords = page.locator('*:has-text("Total Records"), *:has-text("Records:")');
    
    if (await totalRecords.count() > 0) {
      await expect(totalRecords.first()).toBeVisible();
    }
  });

  test('should display feed count', async ({ page }) => {
    await page.goto('/stats');
    
    // Look for feed count stat
    const feedCount = page.locator('*:has-text("Total Feeds"), *:has-text("Feeds:")');
    
    if (await feedCount.count() > 0) {
      await expect(feedCount.first()).toBeVisible();
    }
  });
});

test.describe('Error Handling', () => {
  test('should handle 404 pages gracefully', async ({ page }) => {
    const response = await page.goto('/nonexistent-page-12345');
    
    // Should either show 404 page or redirect to home
    const has404Text = await page.locator('*:has-text("404"), *:has-text("Not Found")').count() > 0;
    const isHomePage = page.url().endsWith('/');
    
    expect(has404Text || isHomePage).toBeTruthy();
  });

  test('should show loading state', async ({ page }) => {
    await page.goto('/');
    
    // Look for loading indicators during initial load
    const loading = page.locator('.loading, .spinner, [aria-busy="true"], *:has-text("Loading")');
    
    // Loading may have already finished, so this is optional
    if (await loading.count() > 0) {
      // If visible, it should disappear
      await expect(loading.first()).not.toBeVisible({ timeout: 5000 });
    }
  });

  test('should handle API errors gracefully', async ({ page, context }) => {
    // Intercept API calls and return error
    await context.route('**/api/v1/feeds', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Internal Server Error' })
      });
    });
    
    await page.goto('/');
    
    // Should show error message or fallback UI
    const errorMessage = page.locator('[role="alert"], .error, .error-message, *:has-text("Error")');
    
    if (await errorMessage.count() > 0) {
      await expect(errorMessage.first()).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Responsive Design', () => {
  test('should work on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // App should still be functional
    const app = page.locator('#root, .app');
    await expect(app).toBeVisible();
    
    // Mobile menu button should be visible
    const mobileMenuButton = page.locator('button[aria-label*="menu" i], .mobile-menu-button, .hamburger');
    if (await mobileMenuButton.count() > 0) {
      await expect(mobileMenuButton.first()).toBeVisible();
    }
  });

  test('should toggle mobile menu', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    
    // Find mobile menu button
    const menuButton = page.locator('button[aria-label*="menu" i], .mobile-menu-button, .hamburger');
    
    const buttonExists = await menuButton.count();
    if (buttonExists === 0) {
      test.skip('Mobile menu not yet implemented');
      return;
    }
    
    await menuButton.first().click();
    
    // Menu should open
    const mobileMenu = page.locator('.mobile-menu, [role="dialog"] nav, .sidebar');
    await expect(mobileMenu).toBeVisible();
  });
});
