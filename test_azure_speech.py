import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv
import time

load_dotenv()

speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv('AZURE_SPEECH_KEY'),
    region=os.getenv('AZURE_SPEECH_REGION')
)
speech_config.speech_recognition_language = "ru-RU"

# Используем микрофон для теста
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

print("🎤 Говорите что-нибудь по-русски...")

def recognized(evt):
    print(f"✅ Recognized: {evt.result.text}")

recognizer.recognized.connect(recognized)
recognizer.start_continuous_recognition()

time.sleep(10)
recognizer.stop_continuous_recognition()
