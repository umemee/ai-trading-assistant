import { test, expect } from '@playwright/test';

test('로그인 플로우', async ({ page }) => {
  await page.goto('http://localhost:8080');
  await page.fill('#pw-input', '2025');
  await page.click('#pw-btn');
  await expect(page.locator('#dashboard')).toBeVisible();
});
