#!/usr/bin/env python3
"""
Скрипт для автоматического подключения к Zoom встрече
"""

import subprocess
import time
import os
import signal
import sys

class ZoomConnector:
    def __init__(self, meeting_url, display=":99"):
        self.meeting_url = meeting_url
        self.display = display
        self.zoom_process = None
    
    def connect_to_meeting(self):
        """Подключается к Zoom встрече по URL"""
        print(f"Connecting to Zoom meeting: {self.meeting_url}")
        
        # Устанавливаем DISPLAY
        env = os.environ.copy()
        env['DISPLAY'] = self.display
        
        # Zoom принимает URL для прямого подключения
        # Формат: zoommtg://zoom.us/join?confno=MEETING_ID
        
        try:
            # Запускаем Zoom с URL встречи
            cmd = ['zoom', f'--url={self.meeting_url}']
            self.zoom_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print(f"✓ Zoom process started (PID: {self.zoom_process.pid})")
            print("Waiting for connection...")
            
            time.sleep(10)  # Даём время на подключение
            
            if self.zoom_process.poll() is None:
                print("✓ Successfully connected to meeting!")
                return True
            else:
                print("✗ Failed to connect")
                return False
        
        except Exception as e:
            print(f"Error connecting to meeting: {e}")
            return False
    
    def disconnect(self):
        """Отключается от встречи"""
        if self.zoom_process:
            print("Disconnecting from meeting...")
            self.zoom_process.terminate()
            time.sleep(2)
            if self.zoom_process.poll() is None:
                self.zoom_process.kill()
            print("✓ Disconnected")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 zoom_connector.py <meeting_url>")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    connector = ZoomConnector(meeting_url)
    
    try:
        if connector.connect_to_meeting():
            print("Press Ctrl+C to disconnect...")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    finally:
        connector.disconnect()
