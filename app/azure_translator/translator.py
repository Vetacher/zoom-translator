import azure.cognitiveservices.speech as speechsdk
from typing import Optional, List, Callable
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

class AzureSpeechTranslator:
    def __init__(self, source_language: str = None, target_languages: List[str] = None):
        self.source_language = source_language or settings.default_source_language
        self.target_languages = target_languages or [settings.default_target_language]
        self.custom_vocabulary = []
        
        self.speech_config = speechsdk.translation.SpeechTranslationConfig(
            subscription=settings.azure_speech_key,
            region=settings.azure_speech_region
        )
        
        self.speech_config.speech_recognition_language = self.source_language
        for target_lang in self.target_languages:
            target_code = target_lang.split('-')[0]
            self.speech_config.add_target_language(target_code)
        
        self.speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "500"
        )
        
        self.recognizer = None
        self.is_running = False
    
    def set_custom_vocabulary(self, vocabulary: List[str]):
        self.custom_vocabulary = vocabulary
        if self.custom_vocabulary and self.recognizer:
            phrase_list = speechsdk.PhraseListGrammar.from_recognizer(self.recognizer)
            for phrase in self.custom_vocabulary:
                phrase_list.addPhrase(phrase)
            logger.info(f"Custom vocabulary set: {len(self.custom_vocabulary)} phrases")
    
    def stop_translation(self):
        if self.recognizer and self.is_running:
            logger.info("Stopping translation...")
            self.recognizer.stop_continuous_recognition()
            self.is_running = False
    
    @staticmethod
    def get_supported_languages():
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
