#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_all_methods():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    try:
        await page.goto("https://us06web.zoom.us/j/88371537219?pwd=MkOo4Q5Cs33oxbFRgVaIgAat4sxXta.1", timeout=15000)
    except:
        pass
    
    await asyncio.sleep(5)
    
    # Cookies + Browser link
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(10)
    
    print("=== Trying different methods to click I Agree ===\n")
    
    # Method 1: By visible text with Playwright
    print("Method 1: get_by_text")
    try:
        await page.get_by_text("I Agree", exact=True).click(timeout=3000)
        print("✓ Success!")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/method1.png')
    
    # Method 2: By role
    print("\nMethod 2: get_by_role")
    try:
        await page.get_by_role("button", name="I Agree").click(timeout=3000)
        print("✓ Success!")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/method2.png')
    
    # Method 3: CSS selector
    print("\nMethod 3: CSS selector")
    try:
        await page.locator('button:has-text("I Agree")').first.click(timeout=3000)
        print("✓ Success!")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/method3.png')
    
    # Method 4: XPath
    print("\nMethod 4: XPath")
    try:
        await page.locator('xpath=//button[contains(text(), "I Agree")]').click(timeout=3000)
        print("✓ Success!")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/method4.png')
    
    # Method 5: Клик по второй кнопке
    print("\nMethod 5: Click 2nd button")
    try:
        buttons = await page.locator('button').all()
        if len(buttons) > 1:
            await buttons[1].click(timeout=3000)
            print(f"✓ Clicked button index 1 (total: {len(buttons)} buttons)")
        else:
            print(f"✗ Only {len(buttons)} button(s) found")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    await asyncio.sleep(5)
    await page.screenshot(path='/tmp/method5_final.png')
    
    print("\n✓ Done! Check /tmp/method*.png")
    
    await browser.close()
    await p.stop()

asyncio.run(test_all_methods())
