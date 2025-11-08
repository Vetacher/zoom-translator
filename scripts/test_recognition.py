#!/usr/bin/env python3
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

print("Recognizing speech from meeting audio...\n")

speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "en-US"

audio_config = speechsdk.audio.AudioConfig(filename='/tmp/meeting_audio.wav')
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# Для длинного аудио используем continuous recognition
all_results = []

def recognized(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"🎤 {evt.result.text}")
        all_results.append(evt.result.text)

recognizer.recognized.connect(recognized)
recognizer.start_continuous_recognition()

import time
time.sleep(35)  # Ждём пока обработается

recognizer.stop_continuous_recognition()

if all_results:
    print(f"\n✓ Total segments recognized: {len(all_results)}")
    print("\nFull transcript:")
    print(" ".join(all_results))
else:
    print("\n⚠️ No speech detected")
