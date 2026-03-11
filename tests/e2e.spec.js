const { test, expect } = require('@playwright/test');

test.describe('Question Paper Generator E2E', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to the local server
    await page.goto('http://127.0.0.1:5000');
  });

  test('Shows error when a text file has less than 100 words', async ({ page }) => {
    // We can simulate an upload
    await page.getByPlaceholder('Enter subject name').fill('Mathematics');
    
    // Create a mock small text file in the browser context via DataTransfer or direct input
    const fileContent = "This is a very short text file. It does not have one hundred words. It should fail the client side validation.";
    
    // Playwright file upload mechanism
    await page.setInputFiles('#file-input', {
      name: 'short_test.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(fileContent)
    });

    // Check that Toast notification appears
    const toastMessage = page.locator('#toast-message');
    await expect(toastMessage).toContainText('100 words');
    
    // The analyze button should still be disabled because the file was rejected
    const analyzeBtn = page.locator('#analyze-btn');
    await expect(analyzeBtn).toBeDisabled();
  });

  test('Accepts 100+ word files and transitions to the next step', async ({ page }) => {
    await page.getByPlaceholder('Enter subject name').fill('Physics');
    
    // Create a mock file with over 100 words
    let longContent = "Word ".repeat(150);
    
    // Playwright file upload mechanism
    await page.setInputFiles('#file-input', {
      name: 'long_test.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(longContent)
    });

    // Check that Toast notification does NOT appear or says success
    // Wait for file details to appear
    const fileDetails = page.locator('#file-details');
    await expect(fileDetails).not.toHaveClass(/d-none/);
    
    // The analyze button should be enabled
    const analyzeBtn = page.locator('#analyze-btn');
    await expect(analyzeBtn).toBeEnabled();
  });

  test('Mobile Responsiveness: Touch targets are at least 44px', async ({ page }) => {
    // Change viewport to mobile
    await page.setViewportSize({ width: 375, height: 812 });

    const btn = page.locator('#mode-pro');
    const box = await btn.boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(44);

    const input = page.locator('#subject-input');
    const inputBox = await input.boundingBox();
    expect(inputBox.height).toBeGreaterThanOrEqual(44);
  });
});
