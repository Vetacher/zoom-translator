#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def fast_join(url):
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--use-fake-ui-for-media-stream'])
    page = await browser.new_page(permissions=['microphone', 'camera'])
    
    print("1. Loading...")
    try:
        await page.goto(url, timeout=15000, wait_until='domcontentloaded')
    except:
        pass
    await asyncio.sleep(5)
    
    print("2. Accept cookies...")
    clicked = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const btn = buttons.find(b => b.textContent.includes('Accept Cookies'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"   Cookies: {clicked}")
    await asyncio.sleep(3)
    
    print("3. Join from browser...")
    clicked = await page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const link = links.find(a => a.textContent.includes('browser'));
            if (link) { link.click(); return true; }
            return false;
        }
    """)
    print(f"   Browser link: {clicked}")
    await asyncio.sleep(8)
    await page.screenshot(path='/tmp/step_browser.png')
    
    print("4. I Agree (ToS)...")
    clicked = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const btn = buttons.find(b => b.textContent.toLowerCase().includes('agree'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"   I Agree: {clicked}")
    await asyncio.sleep(8)
    await page.screenshot(path='/tmp/step_agree.png')
    
    print("5. Use microphone...")
    clicked = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const btn = buttons.find(b => b.textContent.includes('microphone'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"   Microphone: {clicked}")
    await asyncio.sleep(5)
    await page.screenshot(path='/tmp/step_mic.png')
    
    print("6. Enter name...")
    try:
        inputs = await page.query_selector_all('input[type="text"]')
        if inputs:
            await inputs[0].fill('AI Translator Bot')
            print(f"   Name: True")
        else:
            print(f"   Name: False (not found)")
    except Exception as e:
        print(f"   Name: False ({e})")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/step_name.png')
    
    print("7. Join...")
    clicked = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const btn = buttons.find(b => b.textContent.toLowerCase().includes('join') || b.textContent.includes('Войти'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"   Join: {clicked}")
    await asyncio.sleep(10)
    await page.screenshot(path='/tmp/step_final.png')
    
    print("\n✓ Done! Check /tmp/step_*.png")
    
    # Не закрываем браузер - оставляем в встрече
    input("Press Enter to close browser...")
    
    await browser.close()
    await p.stop()

asyncio.run(fast_join("https://us06web.zoom.us/j/87862831635?pwd=lOKd8Oze4vX7RYb2G0HTlwnMHRYoin.1"))
