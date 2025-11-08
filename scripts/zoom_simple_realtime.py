#!/usr/bin/env python3
import subprocess
import time
import os
import threading
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

print("=== Zoom Simple Real-Time Translator ===\n")

# Запускаем Zoom
os.environ['DISPLAY'] = ':100'
meeting_url = "https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1"

print("1. Starting Zoom...")
zoom_proc = subprocess.Popen(f'zoom --url="{meeting_url}"', shell=True, env=os.environ)
time.sleep(20)
print("   ✓ Zoom connected\n")

print("2. Starting continuous audio capture and recognition...\n")

# Настраиваем Azure Speech для работы с файлом
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "en-US"

# Запускаем parecord в фоне
fifo_path = '/tmp/zoom_audio_fifo'
if os.path.exists(fifo_path):
    os.remove(fifo_path)
os.mkfifo(fifo_path)

record_proc = subprocess.Popen([
    'parecord',
    '--device=zoom_capture.monitor',
    '--format=s16le',
    '--rate=16000',
    '--channels=1',
    fifo_path
])

time.sleep(2)

# Используем AudioInputStream
audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
pull_stream = speechsdk.audio.PullAudioInputStream(audio_format)

# Читаем из FIFO в отдельном потоке
def read_audio():
    with open(fifo_path, 'rb') as f:
        while True:
            data = f.read(3200)
            if not data:
                break
            pull_stream.write(data)

audio_thread = threading.Thread(target=read_audio, daemon=True)
audio_thread.start()

# Создаём recognizer
audio_config = speechsdk.audio.AudioConfig(stream=pull_stream)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

def recognized(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"\n🎤 Recognized: {evt.result.text}")

recognizer.recognized.connect(recognized)
recognizer.start_continuous_recognition()

print("✓ Listening... Speak in English!")
print("Press Ctrl+C to stop\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nStopping...")
    recognizer.stop_continuous_recognition()
    record_proc.terminate()
    zoom_proc.terminate()
    pull_stream.close()
    print("✓ Stopped")
