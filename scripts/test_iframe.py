#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_iframe():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    
    try:
        await page.goto("https://us06web.zoom.us/j/88371537219?pwd=MkOo4Q5Cs33oxbFRgVaIgAat4sxXta.1", timeout=15000)
    except:
        pass
    
    await asyncio.sleep(5)
    
    # Cookies + Browser
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(15)
    
    print("=== Checking for iframes ===")
    
    frames = page.frames
    print(f"Total frames: {len(frames)}")
    
    for i, frame in enumerate(frames):
        print(f"\nFrame {i}: {frame.url}")
        
        try:
            buttons = await frame.locator('button').all()
            print(f"  Buttons found: {len(buttons)}")
            
            for j, btn in enumerate(buttons):
                try:
                    is_visible = await btn.is_visible()
                    if is_visible:
                        text = await btn.text_content()
                        text = text.strip() if text else ""
                        print(f"    Button {j}: '{text}'")
                        
                        # Ищем именно "I Agree", не "I Disagree"
                        if text == 'I Agree':
                            print(f"    >>> Found 'I Agree' button! Clicking...")
                            await btn.click()
                            await asyncio.sleep(5)
                            await page.screenshot(path='/tmp/iframe_agreed.png')
                            print("    ✓ Clicked I Agree!")
                            break
                except:
                    pass
                    
        except Exception as e:
            print(f"  Error: {e}")
    
    await asyncio.sleep(3)
    await page.screenshot(path='/tmp/iframe_final.png')
    print("\n✓ Done!")
    
    await browser.close()
    await p.stop()

asyncio.run(test_iframe())
