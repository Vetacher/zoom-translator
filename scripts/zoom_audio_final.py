#!/usr/bin/env python3
import subprocess
import os
import asyncio
from playwright.async_api import async_playwright
import sys

async def join_zoom(meeting_url):
    print("=== Zoom Bot - Connecting to Meeting ===\n")
    
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--use-fake-ui-for-media-stream']
    )
    page = await browser.new_page(permissions=['microphone', 'camera'])
    
    # Step 1: Load page
    print("1. Loading page...")
    try:
        await page.goto(meeting_url, timeout=15000)
    except:
        pass
    await asyncio.sleep(5)
    
    # Step 2: Accept cookies
    print("2. Accepting cookies...")
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    
    # Step 3: Click "Join from browser"
    print("3. Clicking 'Join from browser'...")
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(15)
    
    # Step 4: Click "I Agree" in iframe
    print("4. Accepting Terms of Service...")
    frames = page.frames
    for frame in frames:
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
    
    # Step 5: Continue without microphone and camera
    print("5. Continuing without microphone and camera...")
    for frame in page.frames:
        try:
            links = await frame.locator('a, button').all()
            for link in links:
                if await link.is_visible():
                    text = await link.text_content()
                    if text and ('without microphone' in text.lower() or 'без микрофона' in text.lower()):
                        await link.click()
                        print("   ✓ Clicked 'Continue without microphone and camera'")
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
    # Step 6: Accept "Use microphone" (second dialog)
    print("6. Accepting 'Use microphone' only...")
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    # Ищем кнопку "Use microphone" (НЕ "Use microphone and camera")
                    if text and 'use microphone' in text.lower() and 'camera' not in text.lower():
                        await btn.click()
                        print("   ✓ Clicked 'Use microphone'")
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
    # Step 7: Check name and join
    print("7. Checking name and joining...")
    for frame in page.frames:
        try:
            # Check if name is already filled
            inputs = await frame.locator('input[type="text"]').all()
            if inputs and len(inputs) > 0:
                current_name = await inputs[0].input_value()
                if not current_name or current_name.strip() == '':
                    await inputs[0].fill('AI Translator Bot')
                    print("   ✓ Name entered")
                else:
                    print(f"   ✓ Name already filled: {current_name}")
            
            # Click Join button
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and ('join' in text.lower() or 'войти' in text.lower()):
                        await btn.click()
                        print("   ✓ Clicked Join")
                        break
        except:
            pass
    
    await asyncio.sleep(10)
    await page.screenshot(path='/tmp/zoom_joined.png')
    
    print("\n✓ Successfully joined meeting!")
    await page.screenshot(path='/tmp/zoom_joined.png')
    print("Screenshot saved: /tmp/zoom_joined.png")
    
    print("\n⏸️  PAUSED - Check if bot joined!")
    print("   1. Connect to meeting and check participants")
    print("   2. Speak in English")
    print("   3. Press Enter to start 30sec recording...\n")
    
    # Ждём подтверждения
    await asyncio.sleep(5)  # даём время подключиться
    
    # НЕ input() - это блокирует async. Просто ждём
    print("Waiting 10 seconds for you to check...")
    await asyncio.sleep(10)
    
    print("\n📡 Starting audio capture (30 seconds)...")
    
    # Запускаем запись
    record_proc = subprocess.Popen([
        'parecord',
        '--device=zoom_capture.monitor',
        '--format=s16le',
        '--rate=16000',
        '--channels=1',
        '/tmp/meeting_audio.raw'
    ])
    
    await asyncio.sleep(30)
    
    record_proc.terminate()
    print("✓ Recording complete!")
    
    # Проверяем и распознаём
    if os.path.exists('/tmp/meeting_audio.raw'):
        size = os.path.getsize('/tmp/meeting_audio.raw')
        print(f"   Captured: {size} bytes")    
    await browser.close()
    await p.stop()

if len(sys.argv) > 1:
    asyncio.run(join_zoom(sys.argv[1]))
else:
    print("Usage: python3 zoom_join_complete.py <zoom_url>")
