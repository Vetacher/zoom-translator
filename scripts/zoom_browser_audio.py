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
    print("=== Zoom Browser Audio Capture ===\n")
    
    p = await async_playwright().start()
    
    # Запускаем с аудио захватом
    browser = await p.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--autoplay-policy=no-user-gesture-required',
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            '--allow-file-access-from-files'
        ]
    )
    
    context = await browser.new_context(
        permissions=['microphone', 'camera'],
        record_video_dir='/tmp/zoom_recording',
        record_video_size={'width': 1280, 'height': 720}
    )
    
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
    
    print("4. Accepting Terms...")
    for frame in page.frames:
        try:
            buttons = await frame.locator('button').all()
            for btn in buttons:
                if await btn.is_visible():
                    text = await btn.text_content()
                    if text and text.strip() == 'I Agree':
                        await btn.click()
                        print("   ✓ Agreed")
                        break
        except:
            pass
    
    await asyncio.sleep(8)
    
    print("5. Continue without camera...")
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
    
    print("6. Use microphone...")
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
    
    print("7. Joining...")
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
                        print("   ✓ Joined")
                        break
        except:
            pass
    
    await asyncio.sleep(10)
    
    print("\n✓ Connected! Recording for 60 seconds...\n")
    
    # Записываем 60 секунд
    await asyncio.sleep(60)
    
    await page.close()
    await context.close()
    await browser.close()
    await p.stop()
    
    print("\n8. Processing video/audio...\n")
    
    # Находим записанное видео
    video_files = os.listdir('/tmp/zoom_recording')
    if video_files:
        video_file = f'/tmp/zoom_recording/{video_files[0]}'
        audio_file = '/tmp/extracted_audio.wav'
        
        print(f"   Found video: {video_file}")
        
        # Извлекаем аудио из видео
        subprocess.run([
            'ffmpeg', '-y', '-i', video_file,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            audio_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            print(f"   ✓ Audio extracted: {audio_file}")
            print("\n9. Recognizing speech...\n")
            
            # Распознаём через Azure Speech
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            speech_config.speech_recognition_language = "en-US"
            
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            
            result = recognizer.recognize_once()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"   🎤 Recognized: {result.text}")
            else:
                print(f"   ⚠️ No speech detected")
        else:
            print("   ✗ No audio in video")
    else:
        print("   ✗ No video recorded")

asyncio.run(join_and_capture("https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1"))
