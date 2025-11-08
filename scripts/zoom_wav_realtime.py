#!/usr/bin/env python3
import subprocess
import time
import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

print("=== Zoom WAV Real-Time Translator ===\n")

os.environ['DISPLAY'] = ':100'
meeting_url = "https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1"

print("1. Starting Zoom...")
zoom_proc = subprocess.Popen(f'zoom --url="{meeting_url}"', shell=True, env=os.environ)
time.sleep(20)
print("   ✓ Zoom connected\n")

print("2. Capturing and recognizing audio in 10-second chunks...\n")

speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "en-US"

chunk_num = 0

try:
    while True:
        chunk_num += 1
        raw_file = f'/tmp/chunk_{chunk_num}.raw'
        wav_file = f'/tmp/chunk_{chunk_num}.wav'
        
        print(f"Recording chunk {chunk_num} (10 seconds)...")
        
        # Записываем 10 секунд
        subprocess.run([
            'timeout', '10',
            'parecord',
            '--device=zoom_capture.monitor',
            '--format=s16le',
            '--rate=16000',
            '--channels=1',
            raw_file
        ])
        
        # Конвертируем в WAV
        subprocess.run([
            'ffmpeg', '-y', '-f', 's16le', '-ar', '16000', '-ac', '1',
            '-i', raw_file, wav_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Распознаём
        audio_config = speechsdk.audio.AudioConfig(filename=wav_file)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        result = recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f"  🎤 Recognized: {result.text}\n")
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print(f"  ⚠️  No speech detected\n")
        
        # Удаляем временные файлы
        os.remove(raw_file)
        os.remove(wav_file)

except KeyboardInterrupt:
    print("\n\nStopping...")
    zoom_proc.terminate()
    print("✓ Stopped")
