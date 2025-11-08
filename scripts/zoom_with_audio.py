#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import subprocess
import time

async def join_and_capture(meeting_url):
    print("=== Zoom Bot with Audio Capture ===\n")
    
    p = await async_playwright().start()
    
    # Запускаем браузер с поддержкой аудио
    browser = await p.chromium.launch(
        headless=True,  # Non-headless для теста
        args=[
            '--no-sandbox',
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            '--autoplay-policy=no-user-gesture-required'
        ]
    )
    
    context = await browser.new_context(
        permissions=['microphone', 'camera'],
        record_video_dir='/tmp/zoom_recording'
    )
    
    page = await context.new_page()
    
    # Шаги подключения (как раньше)
    print("1. Loading page...")
    try:
        await page.goto(meeting_url, timeout=15000)
    except:
        pass
    await asyncio.sleep(5)
    
    print("2. Accepting cookies...")
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    
    print("3. Clicking 'Join from browser'...")
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(15)
    
    print("4. Accepting Terms of Service...")
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and text.strip() == 'I Agree':
                        await btn.click()
                        print("   ✓ Clicked I Agree")
                        break
        except:
            pass
    
    await asyncio.sleep(8)
    
    print("5. Continuing without camera...")
    for frame in page.frames:
        try:
            links = await frame.locator('a, button').all()
            for link in links:
                if await link.is_visible():
                    text = await link.text_content()
                    if text and 'without microphone' in text.lower():
                        await link.click()
                        print("   ✓ Clicked 'Continue without'")
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
    print("6. Accepting microphone...")
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and 'use microphone' in text.lower() and 'camera' not in text.lower():
                        await btn.click()
                        print("   ✓ Clicked 'Use microphone'")
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
    print("7. Joining meeting...")
    for frame in page.frames:
        try:
            inputs = await frame.locator('input[type="text"]').all()
            if inputs and len(inputs) > 0:
                current_name = await inputs[0].input_value()
                if not current_name or current_name.strip() == '':
                    await inputs[0].fill('AI Translator Bot')
                    print("   ✓ Name entered")
            
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and 'join' in text.lower():
                        await btn.click()
                        print("   ✓ Clicked Join")
                        break
        except:
            pass
    
    await asyncio.sleep(10)
    
    print("\n✓ Joined meeting! Now listening for audio...\n")
    
    # Держим браузер открытым и слушаем
    print("Recording audio for 30 seconds...")
    await asyncio.sleep(30)
    
    await page.screenshot(path='/tmp/zoom_listening.png')
    print("\n✓ Screenshot saved: /tmp/zoom_listening.png")
    
    await context.close()
    await browser.close()
    await p.stop()

asyncio.run(join_and_capture("https://us06web.zoom.us/j/82876790232?pwd=1nel12sglzNggWQPbE8igISw3MZ630.1"))
