import azure.cognitiveservices.speech as speechsdk
from typing import Optional, List, Callable
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class AzureSpeechTranslator:
    """Класс для работы с Azure Speech Translation"""
    
    def __init__(self, source_language: str = None, target_languages: List[str] = None):
        """
        Инициализирует Azure Speech Translator
        
        Args:
            source_language: Исходный язык (например, 'ru-RU')
            target_languages: Список языков для перевода (например, ['en-US', 'de-DE'])
        """
        self.source_language = source_language or settings.default_source_language
        self.target_languages = target_languages or [settings.default_target_language]
        self.custom_vocabulary = []
        
        # Конфигурация Azure Speech
        self.speech_config = speechsdk.translation.SpeechTranslationConfig(
            subscription=settings.azure_speech_key,
            region=settings.azure_speech_region
        )
        
        # Устанавливаем языки
        self.speech_config.speech_recognition_language = self.source_language
        for target_lang in self.target_languages:
            # Преобразуем формат языка: 'en-US' -> 'en'
            target_code = target_lang.split('-')[0]
            self.speech_config.add_target_language(target_code)
        
        # Настройки качества
        self.speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "500"
        )
        
        self.recognizer = None
        self.is_running = False
    
    def set_custom_vocabulary(self, vocabulary: List[str]):
        """
        Устанавливает кастомный вокабуляр для улучшения распознавания
        
        Args:
            vocabulary: Список специальных слов/фраз
        """
        self.custom_vocabulary = vocabulary
        
        if self.custom_vocabulary and self.recognizer:
            # Создаём phrase list для улучшения распознавания
            phrase_list = speechsdk.PhraseListGrammar.from_recognizer(self.recognizer)
            for phrase in self.custom_vocabulary:
                phrase_list.addPhrase(phrase)
            
            logger.info(f"Custom vocabulary set: {len(self.custom_vocabulary)} phrases")
    
    async def start_translation_from_audio_stream(
        self, 
        audio_stream,
        on_recognizing: Optional[Callable] = None,
        on_recognized: Optional[Callable] = None,
        on_translated: Optional[Callable] = None
    ):
        """
        Начинает перевод из аудио потока
        
        Args:
            audio_stream: Аудио поток для обработки
            on_recognizing: Callback для промежуточных результатов распознавания
            on_recognized: Callback для финальных результатов распознавания
            on_translated: Callback для результатов перевода
        """
        try:
            # Настраиваем аудио конфигурацию
            audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
            
            # Создаём recognizer
            self.recognizer = speechsdk.translation.TranslationRecognizer(
                translation_config=self.speech_config,
                audio_config=audio_config
            )
            
            # Применяем кастомный вокабуляр если есть
            if self.custom_vocabulary:
                self.set_custom_vocabulary(self.custom_vocabulary)
            
            # Подключаем callback'и
            def recognizing_handler(evt):
                if on_recognizing:
                    result = {
                        'text': evt.result.text,
                        'language': self.source_language
                    }
                    asyncio.create_task(on_recognizing(result))
            
            def recognized_handler(evt):
                if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
                    # Исходный текст
                    source_text = evt.result.text
                    
                    # Переводы
                    translations = {}
                    for target_lang in self.target_languages:
                        target_code = target_lang.split('-')[0]
                        if target_code in evt.result.translations:
                            translations[target_lang] = evt.result.translations[target_code]
                    
                    if on_recognized:
                        asyncio.create_task(on_recognized({
                            'source_text': source_text,
                            'source_language': self.source_language
                        }))
                    
                    if on_translated and translations:
                        asyncio.create_task(on_translated({
                            'source_text': source_text,
                            'translations': translations
                        }))
                    
                    logger.info(f"Recognized: {source_text}")
                    logger.info(f"Translations: {translations}")
            
            def canceled_handler(evt):
                logger.error(f"Translation canceled: {evt.reason}")
                if evt.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {evt.error_details}")
                self.is_running = False
            
            # Подключаем обработчики
            self.recognizer.recognizing.connect(recognizing_handler)
            self.recognizer.recognized.connect(recognized_handler)
            self.recognizer.canceled.connect(canceled_handler)
            
            # Запускаем непрерывное распознавание
            logger.info("Starting continuous translation...")
            self.recognizer.start_continuous_recognition()
            self.is_running = True
            
            # Ждём пока работает
            while self.is_running:
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Error in translation: {e}")
            self.is_running = False
            raise
    
    def stop_translation(self):
        """Останавливает перевод"""
        if self.recognizer and self.is_running:
            logger.info("Stopping translation...")
            self.recognizer.stop_continuous_recognition()
            self.is_running = False
    
    @staticmethod
    def get_supported_languages():
        """Возвращает список поддерживаемых языков"""
        return {
            'ru-RU': '🇷🇺 Русский',
            'en-US': '🇺🇸 English (US)',
            'en-GB': '🇬🇧 English (UK)',
            'de-DE': '🇩🇪 Deutsch',
            'fr-FR': '🇫🇷 Français',
            'es-ES': '🇪🇸 Español',
            'it-IT': '🇮🇹 Italiano',
            'zh-CN': '🇨🇳 中文',
            'ja-JP': '🇯🇵 日本語',
            'ko-KR': '🇰🇷 한국어',
            'pt-BR': '🇧🇷 Português',
            'ar-SA': '🇸🇦 العربية',
            'nl-NL': '🇳🇱 Nederlands',
            'pl-PL': '🇵🇱 Polski',
            'tr-TR': '🇹🇷 Türkçe'
        }


class AudioStreamWrapper:
    """Обёртка для аудио потока для работы с Azure Speech SDK"""
    
    def __init__(self):
        self.audio_buffer = []
        self.is_closed = False
    
    def write(self, audio_data):
        """Добавляет аудио данные в буфер"""
        if not self.is_closed:
            self.audio_buffer.append(audio_data)
    
    def read(self, size):
        """Читает аудио данные из буфера"""
        if self.audio_buffer:
            return self.audio_buffer.pop(0)
        return b''
    
    def close(self):
        """Закрывает поток"""
        self.is_closed = True
