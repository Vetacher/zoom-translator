#!/usr/bin/env python3
import subprocess
import time
import os
import threading
import azure.cognitiveservices.speech as speechsdk
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from telegram import Bot
import asyncio
from dotenv import load_dotenv

load_dotenv()

class ZoomRealtimeTranslator:
    def __init__(self):
        # Azure Speech
        self.speech_key = os.getenv('AZURE_SPEECH_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION')
        
        # Azure Translator
        self.translator_key = os.getenv('AZURE_TRANSLATOR_KEY')
        self.translator_region = os.getenv('AZURE_TRANSLATOR_REGION')
        self.translator_endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT')
        
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        self.zoom_process = None
        self.is_running = False
        
    def start_zoom(self, meeting_url):
        print("1. Starting Zoom...")
        os.environ['DISPLAY'] = ':100'
        
        zoom_cmd = f'zoom --url="{meeting_url}"'
        self.zoom_process = subprocess.Popen(zoom_cmd, shell=True, env=os.environ)
        
        print("   Waiting for Zoom to connect...")
        time.sleep(20)
        print("   ✓ Zoom should be connected\n")
    
    async def send_telegram(self, text):
        try:
            bot = Bot(token=self.telegram_token)
            await bot.send_message(chat_id=self.telegram_chat_id, text=text)
        except Exception as e:
            print(f"   ⚠️ Telegram error: {e}")
    
    def translate_text(self, text, target_lang='ru'):
        try:
            client = TextTranslationClient(
                endpoint=self.translator_endpoint,
                credential=AzureKeyCredential(self.translator_key),
                region=self.translator_region
            )
            
            result = client.translate(
                body=[{"text": text}],
                to_language=[target_lang],
                from_language='en'
            )
            
            return result[0].translations[0].text
        except Exception as e:
            print(f"   ⚠️ Translation error: {e}")
            return text
    
    def recognized_callback(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            original = evt.result.text
            print(f"\n   🎤 Original: {original}")
            
            # Переводим
            translated = self.translate_text(original, 'ru')
            print(f"   🌐 Translated: {translated}")
            
            # Отправляем в Telegram
            message = f"🗣️ {original}\n\n🌐 {translated}"
            asyncio.run(self.send_telegram(message))
    
    def start_recognition(self):
        print("2. Starting real-time speech recognition...\n")
        
        # Создаём push audio stream
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1
        )
        
        push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        
        # Speech recognizer
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        speech_config.speech_recognition_language = "en-US"
        
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        # Подключаем callback
        recognizer.recognized.connect(self.recognized_callback)
        
        # Запускаем continuous recognition
        recognizer.start_continuous_recognition()
        
        print("   ✓ Recognition started")
        print("   📡 Listening for speech...\n")
        
        # Захватываем аудио из zoom_capture.monitor
        record_process = subprocess.Popen(
            ['parecord', '--format=s16le', '--rate=16000', '--channels=1', '--device=zoom_capture.monitor'],
            stdout=subprocess.PIPE
        )

        self.is_running = True
        
        try:
            while self.is_running:
                data = record_process.stdout.read(3200)  # 0.1 sec chunks
                if data:
                    push_stream.write(data)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
        finally:
            recognizer.stop_continuous_recognition()
            record_process.terminate()
            push_stream.close()
    
    def run(self, meeting_url):
        print("=== Zoom Real-Time Translator ===\n")
        
        self.start_zoom(meeting_url)
        self.start_recognition()
        
        if self.zoom_process:
            self.zoom_process.terminate()
        
        print("✓ Stopped")

if __name__ == "__main__":
    translator = ZoomRealtimeTranslator()
    
    meeting_url = "https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1"
    
    translator.run(meeting_url)
