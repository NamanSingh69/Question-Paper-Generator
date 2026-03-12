import asyncio
from playwright.async_api import async_playwright
import os

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to production site...")
        await page.goto("https://question-paper-generator-cguzcajme.vercel.app")
        
        print("Filling subject...")
        await page.fill("#subject-input", "Quantum Physics")
        
        print("Uploading file...")
        file_path = os.path.abspath("tests/sample.txt")
        # Ensure the test file exists
        if not os.path.exists(file_path):
             with open(file_path, "w") as f:
                 f.write("This is a sample text file with some content to test the Question Paper Generator.\n" * 20)
        
        await page.set_input_files("#file-input", file_path)
        
        print("Clicking Analyze Content...")
        await page.click("#analyze-btn")
        
        print("Waiting for Step 2 (Configuration) to become active...")
        # After analysis, it jumps to step 2 automatically if successful
        await page.wait_for_selector("#generate-btn", state="visible", timeout=15000)
        
        print("Clicking Generate Exam Paper...")
        await page.click("#generate-btn")
        
        print("Waiting for questions to render...")
        try:
             # Wait for at least one question card to render
             await page.wait_for_selector(".question-card", state="visible", timeout=30000)
             print("SUCCESS! Questions rendered on the screen.")
        except Exception as e:
             print("FAILED to render questions:", e)
             # Let's check for any toasts
             toasts = await page.evaluate("document.getElementById('toast-message')?.innerText")
             print("Toast message (if any):", toasts)
             
        await page.screenshot(path="tests/final-result.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
