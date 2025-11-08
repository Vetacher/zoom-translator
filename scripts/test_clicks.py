#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_clicks():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    
    print("Loading page...")
    try:
        await page.goto("https://us06web.zoom.us/j/87862831635?pwd=lOKd8Oze4vX7RYb2G0HTlwnMHRYoin.1", 
                       timeout=15000, wait_until='domcontentloaded')
    except:
        print("Timeout, but continuing...")
    
    await asyncio.sleep(5)
    
    print("\n=== Finding buttons ===")
    buttons = await page.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            return btns.map(b => ({
                text: b.textContent.trim(),
                visible: b.offsetParent !== null,
                disabled: b.disabled
            }));
        }
    """)
    
    for i, btn in enumerate(buttons):
        print(f"{i}: {btn}")
    
    print("\n=== Trying to click ACCEPT COOKIES ===")

    # Метод 1: Прямой клик по индексу кнопки
    clicked1 = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const acceptBtn = buttons.find(b => b.textContent.includes('Accept Cookies'));
            if (acceptBtn) { 
                acceptBtn.click(); 
                return true; 
            }
            return false;
        }
    """)
    print(f"Method 1 (find by text): {clicked1}")

    # Метод 2: Playwright locator
    try:
        await page.locator('button:has-text("ACCEPT")').click(timeout=3000)
        print("Method 2 (locator): Success")
    except Exception as e:
        print(f"Method 2 (locator): Failed - {e}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/test2.png')
    
    # Метод 3: Клик по кнопке 19 напрямую
    clicked3 = await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            if (buttons[19]) {
                buttons[19].click();
                return true;
            }
            return false;
        }
    """)
    print(f"Method 3 (by index 19): {clicked3}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/test3.png')
    
    print("\n✓ Done! Check /tmp/test*.png")
    
    await browser.close()
    await p.stop()

asyncio.run(test_clicks())
