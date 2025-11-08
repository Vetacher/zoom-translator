#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import subprocess
import os
import time
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

async def join_and_capture(meeting_url):
    print("=== Zoom Browser + PulseAudio Capture ===\n")
    
    # Убеждаемся что sink есть
    subprocess.run(['pactl', 'set-default-sink', 'zoom_capture'], stderr=subprocess.DEVNULL)
    
    p = await async_playwright().start()
    
    # Запускаем браузер с аудио через PulseAudio
    browser = await p.chromium.launch(
        headless=False,  # Non-headless чтобы браузер использовал PulseAudio
        args=[
            '--no-sandbox',
            '--autoplay-policy=no-user-gesture-required',
            '--enable-features=PulseaudioLoopbackForScreenCast'
        ],
        env={**os.environ, 'DISPLAY': ':100'}
    )
    
    context = await browser.new_context(permissions=['microphone', 'camera'])
    page = await context.new_page()
    
    print("1. Connecting...")
    try:
        await page.goto(meeting_url, timeout=15000)
    except:
        pass
    await asyncio.sleep(5)
    
    await page.evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Accept'))?.click()")
    await asyncio.sleep(3)
    await page.evaluate("Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('browser'))?.click()")
    await asyncio.sleep(15)
    # Сначала кликаем "I Agree" на главной странице
    print("   Accepting Terms on main page...")
    try:
        agree_button = page.locator('button:has-text("I Agree")')
        if await agree_button.count() > 0:
            await agree_button.click()
            print("   ✓ Clicked I Agree on main page")
            await asyncio.sleep(5)
    except:
        pass
    
    # Потом в iframe (если есть)
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and text.strip() == 'I Agree':
                        await btn.click()
                        print("   ✓ Clicked I Agree in iframe")
                        break
        except:
            pass
    
    await asyncio.sleep(8)

    for frame in page.frames:
        try:
            links = await frame.locator('a, button').all()
            for link in links:
                if await link.is_visible():
                    text = await link.text_content()
                    if text and 'without microphone' in text.lower():
                        await link.click()
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and 'use microphone' in text.lower() and 'camera' not in text.lower():
                        await btn.click()
                        break
        except:
            pass
    
    await asyncio.sleep(5)
    
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
                        break
        except:
            pass
    
    await asyncio.sleep(10)
    print("✓ Joined!\n")
    await page.screenshot(path='/tmp/zoom_after_join.png')
    print("   Screenshot saved: /tmp/zoom_after_join.png")
    print("\n⏸️  PAUSED - Check if bot joined the meeting!")
    print("   1. Connect to the meeting from your computer")
    print("   2. Check if 'AI Translator Bot' is in participants")
    print("   3. Press Enter here to start recording...\n")
    input("Press Enter when ready...")

    # Ждём чтобы браузер начал выводить аудио
    await asyncio.sleep(5)
    
    # Находим sink-input от Chromium
    result = subprocess.run(['pactl', 'list', 'sink-inputs'], capture_output=True, text=True)
    print("Sink inputs:")
    print(result.stdout)
    
    # Запускаем запись
    print("\n3. Recording for 30 seconds...")
    record_proc = subprocess.Popen([
        'parecord',
        '--device=zoom_capture.monitor',
        '--format=s16le',
        '--rate=16000',
        '--channels=1',
        '/tmp/browser_audio.raw'
    ])
    
    await asyncio.sleep(30)
    
    record_proc.terminate()
    print("\n✓ Recording complete!")
    
    # Проверяем размер
    if os.path.exists('/tmp/browser_audio.raw'):
        size = os.path.getsize('/tmp/browser_audio.raw')
        print(f"   Captured: {size} bytes")
        
        if size > 1000:
            # Конвертируем и распознаём
            subprocess.run([
                'ffmpeg', '-y', '-f', 's16le', '-ar', '16000', '-ac', '1',
                '-i', '/tmp/browser_audio.raw', '/tmp/browser_audio.wav'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print("\n4. Recognizing speech...")
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            speech_config.speech_recognition_language = "en-US"
            audio_config = speechsdk.audio.AudioConfig(filename='/tmp/browser_audio.wav')
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            
            result = recognizer.recognize_once()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"   🎤 Recognized: {result.text}")
            else:
                print("   ⚠️ No speech detected")
        else:
            print("   ✗ No audio captured")
    
    await context.close()
    await browser.close()
    await p.stop()

asyncio.run(join_and_capture("https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1"))
