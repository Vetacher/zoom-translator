#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_coords():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    try:
        await page.goto("https://us06web.zoom.us/j/88371537219?pwd=MkOo4Q5Cs33oxbFRgVaIgAat4sxXta.1", timeout=15000)
    except:
        pass
    
    await asyncio.sleep(5)
    
    # Cookies
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    
    # Browser
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(10)
    
    await page.screenshot(path='/tmp/before_coord_click.png')
    print("Screenshot saved, now clicking at button coordinates...")
    
    # Кликаем по центру экрана где обычно кнопка "I Agree"
    # На скриншоте кнопка примерно в центре справа
    await page.mouse.click(700, 224)  # Координаты кнопки "I Agree"
    
    await asyncio.sleep(5)
    await page.screenshot(path='/tmp/after_coord_click.png')
    print("✓ Clicked! Check screenshots")
    
    await browser.close()
    await p.stop()

asyncio.run(test_coords())

