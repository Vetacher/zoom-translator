#!/usr/bin/env python3
import subprocess
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

print("Testing Azure Speech recognition...\n")

# Простой тест с файлом
print("1. Testing with file...")
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "en-US"

audio_config = speechsdk.audio.AudioConfig(filename="/tmp/zoom_audio.wav")
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

result = recognizer.recognize_once()

if result.reason == speechsdk.ResultReason.Canceled:
    cancellation = result.cancellation_details
    print(f"   ✗ Canceled: {cancellation.reason}")
    print(f"   ✗ Error details: {cancellation.error_details}")

if result.reason == speechsdk.ResultReason.RecognizedSpeech:
    print(f"   ✓ Recognized: {result.text}")
elif result.reason == speechsdk.ResultReason.NoMatch:
    print(f"   ✗ No speech detected")
else:
    print(f"   ✗ Error: {result.reason}")

print("\n2. Testing with live stream...")

# Тест с потоком
audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

speech_config2 = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config2.speech_recognition_language = "en-US"
recognizer2 = speechsdk.SpeechRecognizer(speech_config=speech_config2, audio_config=audio_config)

def recognized(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"   ✓ Live: {evt.result.text}")

recognizer2.recognized.connect(recognized)
recognizer2.start_continuous_recognition()

print("   Recording 10 seconds from Zoom...")

# Захватываем из zoom_capture.monitor
proc = subprocess.Popen(
    ['parecord', '--device=zoom_capture.monitor', '--format=s16le', '--rate=16000', '--channels=1'],
    stdout=subprocess.PIPE
)

import time
for i in range(100):  # 10 seconds
    data = proc.stdout.read(3200)
    if data:
        push_stream.write(data)
    time.sleep(0.1)

recognizer2.stop_continuous_recognition()
proc.terminate()
push_stream.close()

print("\n✓ Test complete!")
