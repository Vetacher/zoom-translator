#!/usr/bin/env python3
"""
Пошаговое подключение к Zoom с промежуточными скриншотами
"""

import asyncio
from playwright.async_api import async_playwright
import sys

async def step_by_step_join(meeting_url):
    print("=" * 60)
    print("Zoom Step-by-Step Connector")
    print("=" * 60)
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream'
        ]
    )
    
    context = await browser.new_context(
        permissions=['microphone', 'camera'],
        viewport={'width': 1920, 'height': 1080}
    )
    
    page = await context.new_page()
    
    # Устанавливаем реальный User-Agent
    await page.set_extra_http_headers({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    
    # Шаг 1: Загрузка страницы
    print("\n[Step 1] Loading page...")
    
    # Не ждём полной загрузки, только DOM
    try:
        await page.goto(meeting_url, timeout=15000, wait_until='domcontentloaded')
    except Exception as e:
        print(f"Load timeout (expected): {e}")
        print("Continuing anyway...")
    
    # Ждём несколько секунд для частичной загрузки
    await asyncio.sleep(10)

    # Шаг 2: Принять cookies
    print("\n[Step 2] Accepting cookies...")
    cookies_accepted = await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent.includes('ACCEPT COOKIES') || 
                    btn.textContent.includes('Accept')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
    """)
    print(f"Cookies button found: {cookies_accepted}")
    await asyncio.sleep(3)
    await page.screenshot(path='/tmp/step2_cookies.png')
    print("✓ Screenshot saved: /tmp/step2_cookies.png")
    input("Press Enter to continue...")
    
    # Шаг 2.5: Кликаем "Join from your browser"
    print("\n[Step 2.5] Clicking 'Join from your browser'...")
    
    browser_join_clicked = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a');
            for (const link of links) {
                const text = link.textContent || link.innerText || '';
                if (text.includes('Join from your browser') ||
                    text.includes('browser')) {
                    link.click();
                    return true;
                }
            }
            return false;
        }
    """)
    
    print(f"Browser join link found: {browser_join_clicked}")
    await asyncio.sleep(10)
    await page.screenshot(path='/tmp/step2_5_browser.png')
    print("✓ Screenshot saved: /tmp/step2_5_browser.png")
    input("Press Enter to continue...")

    # Шаг 2.6: Принять Terms of Service (второй раз)
    print("\n[Step 2.6] Accepting Terms of Service (2nd time)...")
    
    agree_clicked = await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = (btn.textContent || btn.innerText || '').toLowerCase();
                if (text.includes('agree')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
    """)
    
    print(f"I Agree button found: {agree_clicked}")
    await asyncio.sleep(5)
    await page.screenshot(path='/tmp/step2_6_agreed.png')
    print("✓ Screenshot saved: /tmp/step2_6_agreed.png")
    input("Press Enter to continue...")

    # Шаг 3: Кликнуть "Use microphone"
    print("\n[Step 3] Clicking 'Use microphone'...")
    mic_clicked = await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent.includes('Use microphone') ||
                    btn.textContent.includes('microphone and camera')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
    """)
    print(f"Microphone button found: {mic_clicked}")
    await asyncio.sleep(5)
    await page.screenshot(path='/tmp/step3_microphone.png')
    print("✓ Screenshot saved: /tmp/step3_microphone.png")
    input("Press Enter to continue...")
    
    # Шаг 4: Ввести имя
    print("\n[Step 4] Entering name...")
    
    # Показываем все input поля
    inputs_info = await page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input');
            return Array.from(inputs).map(inp => ({
                type: inp.type,
                placeholder: inp.placeholder,
                id: inp.id,
                visible: inp.offsetParent !== null
            }));
        }
    """)
    print(f"Found {len(inputs_info)} input fields:")
    for i, info in enumerate(inputs_info):
        print(f"  {i}: {info}")
    
    # Пробуем ввести имя
    try:
        name_input = await page.wait_for_selector('input[type="text"]', timeout=5000, state='visible')
        await name_input.fill("AI Translator Bot")
        print("✓ Name entered")
    except:
        print("✗ Could not find name input")
    
    await asyncio.sleep(2)
    await page.screenshot(path='/tmp/step4_name.png')
    print("✓ Screenshot saved: /tmp/step4_name.png")
    input("Press Enter to continue...")
    
    # Шаг 5: Нажать Join
    print("\n[Step 5] Clicking Join button...")
    join_clicked = await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent.includes('Join') || 
                    btn.textContent.includes('Войти')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
    """)
    print(f"Join button found: {join_clicked}")
    await asyncio.sleep(10)
    await page.screenshot(path='/tmp/step5_joined.png')
    print("✓ Screenshot saved: /tmp/step5_joined.png")
    
    print("\n" + "=" * 60)
    print("All steps completed!")
    print("Check screenshots in /tmp/step*.png")
    print("=" * 60)
    
    input("Press Enter to close browser...")
    
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 zoom_step_by_step.py <meeting_url>")
        sys.exit(1)
    
    asyncio.run(step_by_step_join(sys.argv[1]))
