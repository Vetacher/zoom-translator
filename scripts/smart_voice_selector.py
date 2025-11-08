#!/usr/bin/env python3
import azure.cognitiveservices.speech as speechsdk
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
import os
from dotenv import load_dotenv

load_dotenv()

class SmartTranslator:
    def __init__(self):
        self.speech_key = os.getenv('AZURE_SPEECH_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION')
        
        # Голоса по полу
        self.voices = {
            'female': 'en-US-JennyNeural',      # Естественный женский
            'male': 'en-US-GuyNeural',          # Профессиональный мужской
            'unknown': 'en-US-AriaNeural'       # По умолчанию
        }
    
    def detect_speaker_gender(self, audio_file):
        """Определяет пол говорящего через анализ аудио"""
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        speech_config.speech_recognition_language = "ru-RU"
        
        # Включаем определение говорящего
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EnableSpeakerDiarization,
            "true"
        )
        
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        results = []
        
        def recognized(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Azure возвращает speaker ID
                speaker_id = evt.result.speaker_id if hasattr(evt.result, 'speaker_id') else None
                results.append({
                    'text': evt.result.text,
                    'speaker': speaker_id
                })
        
        recognizer.recognized.connect(recognized)
        recognizer.start_continuous_recognition()
        
        # Даём время на распознавание
        import time
        time.sleep(10)
        recognizer.stop_continuous_recognition()
        
        # Определяем пол по частотам (грубая оценка)
        # В реальности используем ML модель или Speaker Recognition API
        return self.analyze_audio_frequency(audio_file)
    
    def analyze_audio_frequency(self, audio_file):
        """Анализирует частоту голоса для определения пола"""
        import wave
        import numpy as np
        
        with wave.open(audio_file, 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            audio_data = np.frombuffer(frames, dtype=np.int16)
            
            # Вычисляем среднюю частоту
            fft = np.fft.fft(audio_data)
            freqs = np.fft.fftfreq(len(fft))
            
            # Упрощенная логика:
            # Женский голос: 165-255 Hz
            # Мужской голос: 85-180 Hz
            dominant_freq = abs(freqs[np.argmax(np.abs(fft))]) * wav.getframerate()
            
            if dominant_freq > 180:
                return 'female'
            elif dominant_freq > 85:
                return 'male'
            else:
                return 'unknown'
    
    def synthesize_with_smart_voice(self, text, output_file, gender='unknown'):
        """Озвучивает с правильным голосом"""
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        
        # Выбираем голос
        voice = self.voices.get(gender, self.voices['unknown'])
        speech_config.speech_synthesis_voice_name = voice
        
        # Высокое качество
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
        )
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        # SSML для естественности
        ssml = f"""
        <speak version='1.0' xml:lang='en-US'>
            <voice name='{voice}'>
                <prosody rate='0.95' pitch='+2%'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        
        print(f"Using voice: {voice} (gender: {gender})")
        synthesizer.speak_ssml_async(ssml).get()
        print(f"✓ Audio saved: {output_file}")


# Тест
if __name__ == "__main__":
    translator = SmartTranslator()
    
    audio_file = '/tmp/test_audio.wav'
    
    print("Detecting speaker gender...")
    gender = translator.detect_speaker_gender(audio_file)
    print(f"Detected: {gender}\n")
    
    # Тестовый текст
    test_text = "Hello, this is a test of automatic voice selection based on speaker gender."
    
    translator.synthesize_with_smart_voice(
        test_text,
        f'/tmp/test_{gender}_voice.wav',
        gender
    )
