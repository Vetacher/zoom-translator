#!/usr/bin/env python3

import asyncio
import logging
import sys
import os
from pathlib import Path
import requests
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import uvicorn
from fastapi import FastAPI, Request

from app.realtime_translator.web_interface import get_web_interface

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Keys
RECALL_API_KEY = os.getenv('RECALL_API_KEY')
BASE_URL = 'https://us-west-2.recall.ai/api/v1'
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY')
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

# AWS Transcribe (опционально)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_VOCABULARY_NAME = os.getenv('AWS_VOCABULARY_NAME')  # Имя custom vocabulary в AWS

WEBHOOK_BASE_URL = os.getenv('WEBHOOK_URL', 'https://zoom-bot-vm.westeurope.cloudapp.azure.com')

class RealtimeTranslator:
    def __init__(self, meeting_url: str):
        self.meeting_url = meeting_url
        self.bot_id = None
        self.openai_client = AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        self.web = get_web_interface()
        self.headers = {
            'Authorization': f'Token {RECALL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Буфер для накопления слов в предложения
        self.sentence_buffer = {}
        
        # Setup webhook endpoint
        self.setup_webhook()
    
    def setup_webhook(self):
        """Setup webhook endpoints for Recall.ai"""
        
        @self.web.app.post("/webhook/transcript")
        async def receive_transcript(request: Request):
            """Receive real-time transcript from Recall.ai"""
            try:
                data = await request.json()
                event = data.get('event')
                
                logger.info(f"📩 Webhook event: {event}")
                
                if event == 'transcript.data':
                    # Финальная транскрипция
                    await self.process_transcript(data, is_partial=False)
                elif event == 'transcript.partial_data':
                    # Частичная транскрипция (для меньшей задержки)
                    await self.process_transcript(data, is_partial=True)
                
                return {"status": "ok"}
                
            except Exception as e:
                logger.error(f"Webhook error: {e}", exc_info=True)
                return {"status": "error", "message": str(e)}
        
        @self.web.app.post("/webhook/bot_events")
        async def receive_bot_events(request: Request):
            """Receive bot status events"""
            try:
                data = await request.json()
                event = data.get('event')
                logger.info(f"🤖 Bot event: {event}")
                return {"status": "ok"}
            except Exception as e:
                logger.error(f"Bot events error: {e}")
                return {"status": "error"}
    
    async def create_bot(self):
        """Create Recall bot with real-time transcription"""
        logger.info("Creating Recall bot with real-time transcription...")
        
        # Определяем провайдера транскрипции
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            logger.info("Using AWS Transcribe with custom vocabulary")
            transcript_provider = {
                "aws_transcribe_streaming": {
                    "credentials": {
                        "access_key_id": AWS_ACCESS_KEY_ID,
                        "secret_access_key": AWS_SECRET_ACCESS_KEY
                    },
                    "region": AWS_REGION,
                    "language_code": "ru-RU"
                }
            }
            
            # Добавляем custom vocabulary если указано
            if AWS_VOCABULARY_NAME:
                transcript_provider["aws_transcribe_streaming"]["vocabulary_name"] = AWS_VOCABULARY_NAME
                logger.info(f"Using custom vocabulary: {AWS_VOCABULARY_NAME}")
        else:
            logger.info("Using Recall.ai streaming transcription")
            transcript_provider = {
                "recallai_streaming": {
                    "language_code": "ru"
                }
            }
        
        bot_data = {
            "meeting_url": self.meeting_url,
            "bot_name": "AI Translator Bot",
            "recording_config": {
                "transcript": {
                    "provider": transcript_provider,
                    "diarization": {
                        "use_separate_streams_when_available": True
                    }
                },
                "realtime_endpoints": [
                    {
                        "type": "webhook",
                        "url": f"{WEBHOOK_BASE_URL}/webhook/transcript",
                        "events": ["transcript.data", "transcript.partial_data"]
                    }
                ]
            }
        }
        
        logger.info(f"📡 Webhook URL: {WEBHOOK_BASE_URL}/webhook/transcript")
        
        response = requests.post(
            f'{BASE_URL}/bot/',
            json=bot_data,
            headers=self.headers
        )
        
        if response.status_code == 201:
            bot = response.json()
            self.bot_id = bot['id']
            logger.info(f"✓ Bot created: {self.bot_id}")
            logger.info(f"✓ Real-time transcription webhook configured")
            
            await self.web.broadcast({
                "type": "system",
                "message": "Bot connected, listening for speech..."
            })
            
            return True
        else:
            logger.error(f"❌ Failed to create bot: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    
    async def process_transcript(self, data: dict, is_partial: bool):
        """Process transcript from Recall.ai webhook"""
        try:
            transcript_data = data.get('data', {}).get('data', {})
            words = transcript_data.get('words', [])
            participant = transcript_data.get('participant', {})
            
            if not words:
                return
            
            # Собираем текст из слов
            text = ' '.join([word['text'] for word in words])
            speaker = participant.get('name') or f"Participant {participant.get('id', 'Unknown')}"
            
            if not text.strip():
                return
            
            # Для частичных результатов - просто показываем
            if is_partial:
                logger.info(f"👤 {speaker} (partial): {text}")
                await self.web.broadcast({
                    "type": "partial_transcript",
                    "speaker": speaker,
                    "text": text
                })
                return
            
            # Для финальных результатов - переводим
            logger.info(f"👤 {speaker}: {text}")
            
            # Переводим
            translation = await self.translate(text)
            logger.info(f"🌍 Translation: {translation}")
            
            # Отправляем в веб-интерфейс
            await self.web.broadcast({
                "type": "translation",
                "speaker": speaker,
                "original": text,
                "translation": translation
            })
            
        except Exception as e:
            logger.error(f"Error processing transcript: {e}", exc_info=True)
    
    async def translate(self, text: str) -> str:
        """Translate text using Azure OpenAI"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate Russian to English. Provide ONLY the translation, no explanations."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return f"[Translation error]"
    
    async def start(self):
        """Start the translator bot"""
        if await self.create_bot():
            logger.info("✓ Bot running and waiting for transcriptions...")
            await self.web.broadcast({
                "type": "system",
                "message": "Ready to translate"
            })
        else:
            logger.error("❌ Failed to start bot")
    
    async def stop(self):
        """Stop the translator bot"""
        if self.bot_id:
            try:
                requests.delete(
                    f'{BASE_URL}/bot/{self.bot_id}',
                    headers=self.headers
                )
                logger.info("✓ Bot deleted")
            except Exception as e:
                logger.error(f"Error deleting bot: {e}")

translator = None

async def run_translator(meeting_url: str):
    global translator
