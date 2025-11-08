#!/usr/bin/env python3
import subprocess
import time
import os
import signal
import asyncio
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

class ZoomDesktopCapture:
    def __init__(self):
        self.zoom_process = None
        self.record_process = None
        
    def join_meeting(self, meeting_url):
        print("=== Zoom Desktop Audio Capture ===\n")
        
        # Устанавливаем DISPLAY
        os.environ['DISPLAY'] = ':100'
        
        print("1. Launching Zoom...")
        # Запускаем Zoom с join URL
        zoom_cmd = f'zoom --url="{meeting_url}"'
        self.zoom_process = subprocess.Popen(
            zoom_cmd,
            shell=True,
            env=os.environ
        )
        
        print("   Waiting for Zoom to start...")
        time.sleep(15)
        
        print("\n2. Starting audio capture...")
        # Захватываем аудио через parecord
        self.record_process = subprocess.Popen([
            'parecord',
            '--format=s16le',
            '--rate=16000',
            '--channels=1',
            '/tmp/zoom_audio.raw'
        ])
        
        print("   Recording to /tmp/zoom_audio.raw")
        print("\n✓ Zoom running and recording audio!")
        print("   Press Ctrl+C to stop...\n")
        
        try:
            # Держим процессы живыми
            while True:
                time.sleep(1)
                
                # Проверяем размер файла
                if os.path.exists('/tmp/zoom_audio.raw'):
                    size = os.path.getsize('/tmp/zoom_audio.raw')
                    print(f"   Recording... {size} bytes captured", end='\r')
                
        except KeyboardInterrupt:
            print("\n\nStopping...")
            self.cleanup()
    
    def cleanup(self):
        print("Cleaning up...")
        
        if self.record_process:
            self.record_process.terminate()
            self.record_process.wait()
        
        if self.zoom_process:
            self.zoom_process.terminate()
            self.zoom_process.wait()
        
        print("✓ Stopped")

if __name__ == "__main__":
    capture = ZoomDesktopCapture()
    
    meeting_url = "https://us06web.zoom.us/j/82876790232?pwd=1nel12sglzNggWQPbE8igISw3MZ630.1"
    
    capture.join_meeting(meeting_url)
