#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_agree():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    
    # Идем сразу к ToS странице после клика cookies и browser link
    try:
        await page.goto("https://us06web.zoom.us/j/87862831635?pwd=lOKd8Oze4vX7RYb2G0HTlwnMHRYoin.1", timeout=15000, wait_until='domcontentloaded')
    except:
        print("Timeout, continuing...")
    await asyncio.sleep(5)
    
    # Клик cookies
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept Cookies'))?.click()")
    await asyncio.sleep(3)
    
    # Клик browser
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(8)
    
    print("=== Checking I Agree page ===")
    
    # Находим все кнопки
    buttons = await page.evaluate("""
        () => Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.textContent.trim(),
            visible: b.offsetParent !== null
        }))
    """)
    
    print("Buttons found:")
    for i, btn in enumerate(buttons):
        if btn['visible']:
            print(f"  {i}: '{btn['text']}'")
    
    # Более детальная проверка кнопок
    print("\nDetailed button check:")
    detailed = await page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            return buttons.map(b => ({
                textContent: b.textContent?.trim(),
                innerText: b.innerText?.trim(),
                innerHTML: b.innerHTML.substring(0, 100),
                ariaLabel: b.getAttribute('aria-label'),
                id: b.id,
                className: b.className
            })).filter(b => 
                b.textContent?.includes('Agree') || 
                b.innerText?.includes('Agree') ||
                b.innerHTML?.includes('Agree') ||
                b.ariaLabel?.includes('Agree')
            );
        }
    """)
    
    for btn in detailed:
        print(f"  {btn}")
    
    # Пробуем кликнуть через селектор текста в innerHTML
    print("\n=== Method 3: Click by selector ===")
    result3 = await page.evaluate("""
        () => {
            const btn = document.querySelector('button:nth-of-type(2)'); // Вторая кнопка (I Agree)
            if (btn) { 
                btn.click(); 
                return 'Clicked button 2';
            }
            return 'Not found';
        }
    """)
    print(f"Result: {result3}")
    
    # Пробуем разные способы клика
    print("\n=== Method 1: Find 'I Agree' ===")
    result1 = await page.evaluate("""
        () => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('I Agree'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"Result: {result1}")
    
    await asyncio.sleep(3)
    await page.screenshot(path='/tmp/agree1.png')
    
    print("\n=== Method 2: Find 'Agree' (lowercase) ===")
    result2 = await page.evaluate("""
        () => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.toLowerCase().includes('agree'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    print(f"Result: {result2}")
    
    await asyncio.sleep(3)
    await page.screenshot(path='/tmp/agree2.png')
    
    print("\n✓ Done!")
    
    await browser.close()
    await p.stop()

asyncio.run(test_agree())
