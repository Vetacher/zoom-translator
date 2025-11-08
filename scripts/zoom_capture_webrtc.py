#!/usr/bin/env python3
import asyncio
import json
from playwright.async_api import async_playwright

class ZoomAudioCapture:
    def __init__(self):
        self.audio_chunks = []
        
    async def join_meeting(self, meeting_url):
        print("=== Zoom WebRTC Audio Capture ===\n")
        
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required']
        )
        
        context = await browser.new_context(permissions=['microphone', 'camera'])
        page = await context.new_page()
        
        # Подключаемся к встрече
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
                            print("   ✓ Clicked")
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
                            print("   ✓ Clicked")
                            break
            except:
                pass
        
        await asyncio.sleep(5)
        
        print("7. Joining meeting...")
        for frame in page.frames:
            try:
                inputs = await frame.locator('input[type="text"]').all()
                if inputs:
                    current_name = await inputs[0].input_value()
                    if not current_name:
                        await inputs[0].fill('AI Translator Bot')
                
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
        print("\n✓ Joined meeting! Capturing audio...\n")
        
        # Простой тест - держим соединение 30 сек
        for i in range(30):
            await asyncio.sleep(1)
            print(f"  Listening... {i+1}/30 seconds")
        
        await page.screenshot(path='/tmp/zoom_audio_test.png')
        print("\n✓ Test complete!")
        
        await context.close()
        await browser.close()
        await p.stop()

async def main():
    print("Starting...")
    capture = ZoomAudioCapture()
    await capture.join_meeting("https://us06web.zoom.us/j/82876790232?pwd=1nel12sglzNggWQPbE8igISw3MZ630.1")

if __name__ == "__main__":
    asyncio.run(main())
