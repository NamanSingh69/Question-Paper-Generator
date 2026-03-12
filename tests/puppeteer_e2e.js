const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    
    // Use the existing 150-word test document to pass word count validation
    const filePath = path.join(__dirname, 'test_upload.txt');

    console.log('Navigating to website...');
    await page.goto('https://question-paper-generator-mu.vercel.app', { waitUntil: 'networkidle2' });

    console.log('Setting subject...');
    await page.type('#subject-input', 'Computer Science');

    console.log('Uploading file...');
    const fileInput = await page.$('#file-input');
    await fileInput.uploadFile(filePath);

    // Wait for the UI to show the file is uploaded (the file details div should become visible)
    await page.waitForSelector('#file-details:not(.d-none)');

    console.log('Clicking analyze button...');
    await page.click('#analyze-btn');

    console.log('Waiting for step 2 (generate button)...');
    await page.waitForSelector('#generate-btn', { visible: true, timeout: 15000 });

    console.log('Clicking generate button...');
    await page.click('#generate-btn');

    console.log('Waiting for questions to render...');
    try {
        await page.waitForSelector('.question-card', { visible: true, timeout: 30000 });
        console.log('SUCCESS: Questions rendered on the screen!');
        await page.screenshot({ path: path.join(__dirname, 'final_success.png'), fullPage: true });
    } catch (e) {
        console.log('FAILED to find questions within 30 seconds.');
        const toastMessage = await page.evaluate(() => document.getElementById('toast-message')?.innerText);
        console.log('Toast:', toastMessage);
        await page.screenshot({ path: path.join(__dirname, 'final_failure.png'), fullPage: true });
    }

    await browser.close();
})();
