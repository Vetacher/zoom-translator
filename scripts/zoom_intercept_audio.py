#!/usr/bin/env python3
import asyncio
import json
import base64
from playwright.async_api import async_playwright
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv

load_dotenv()

class ZoomAudioInterceptor:
    def __init__(self):
        self.audio_queue = asyncio.Queue()
        
        # Azure Speech config
        speech_key = os.getenv('AZURE_SPEECH_KEY')
        speech_region = os.getenv('AZURE_SPEECH_REGION')
        
        if not speech_key or not speech_region:
            raise ValueError("Missing AZURE_SPEECH_KEY or AZURE_SPEECH_REGION in .env")
        
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        self.speech_config.speech_recognition_language = "en-US"
        
    async def join_meeting(self, meeting_url):
        print("=== Zoom WebRTC Audio Interceptor ===\n")
        
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required']
        )
        
        context = await browser.new_context(permissions=['microphone', 'camera'])
        page = await context.new_page()
        
        # Инжектим код для перехвата WebRTC аудио
        await page.add_init_script("""
            // Перехватываем RTCPeerConnection
            const OriginalRTCPeerConnection = window.RTCPeerConnection;
            
            window.RTCPeerConnection = function(...args) {
                const pc = new OriginalRTCPeerConnection(...args);
                
                // Перехватываем ontrack событие
                pc.addEventListener('track', (event) => {
                    if (event.track.kind === 'audio') {
                        console.log('Audio track detected!');
                        
                        const stream = new MediaStream([event.track]);
                        const audioContext = new AudioContext({sampleRate: 16000});
                        const source = audioContext.createMediaStreamSource(stream);
                        const processor = audioContext.createScriptProcessor(4096, 1, 1);
                        
                        processor.onaudioprocess = (e) => {
                            const inputData = e.inputBuffer.getChannelData(0);
                            const pcmData = new Int16Array(inputData.length);
                            
                            for (let i = 0; i < inputData.length; i++) {
                                pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                            }
                            
                            // Отправляем в Python
                            window.audioData = Array.from(pcmData);
                        };
                        
                        source.connect(processor);
                        processor.connect(audioContext.destination);
                    }
                });
                
                return pc;
            };
        """)
        
        # Подключаемся к встрече (копируем из предыдущего скрипта)
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
        print("\n✓ Joined meeting! Intercepting audio...\n")
        
        # Читаем аудио данные
        for i in range(60):
            await asyncio.sleep(1)
            
            try:
                audio_data = await page.evaluate("() => window.audioData")
                if audio_data:
                    print(f"  Second {i+1}/60 - Audio data captured: {len(audio_data)} samples")
                    # Здесь можно отправить в Azure Speech
                else:
                    print(f"  Second {i+1}/60 - Waiting for audio...")
            except:
                print(f"  Second {i+1}/60 - No audio yet...")
        
        print("\n✓ Capture complete!")
        
        await context.close()
        await browser.close()
        await p.stop()

async def main():
    interceptor = ZoomAudioInterceptor()
    await interceptor.join_meeting("https://us06web.zoom.us/j/82876790232?pwd=1nel12sglzNggWQPbE8igISw3MZ630.1")

if __name__ == "__main__":
    asyncio.run(main())
