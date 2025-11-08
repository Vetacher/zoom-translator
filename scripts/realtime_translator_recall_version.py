#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path
import requests
import json
import base64
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import uvicorn
from fastapi import FastAPI, Request

# Azure Speech SDK
import azure.cognitiveservices.speech as speechsdk

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

# Azure Speech Services
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION', 'westeurope')

WEBHOOK_BASE_URL = os.getenv('WEBHOOK_URL', 'https://zoom-bot-vm.westeurope.cloudapp.azure.com')

# Load glossary
GLOSSARY_PATH = Path(__file__).parent.parent / 'config' / 'translation_glossary.json'


class GlossaryManager:
    """Manages translation glossary"""
    
    def __init__(self, glossary_path: Path):
        self.glossary = {}
        self.load_glossary(glossary_path)
    
    def load_glossary(self, path: Path):
        """Load glossary from JSON file"""
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    self.glossary = json.load(f)
                logger.info(f"✅ Loaded glossary with {len(self.glossary)} terms")
            else:
                logger.warning(f"⚠️ Glossary file not found: {path}")
        except Exception as e:
            logger.error(f"Error loading glossary: {e}")
    
    def build_prompt(self, limit: int = 30) -> str:
        """Build glossary prompt for GPT"""
        if not self.glossary:
            return ""
        
        terms = [
            f"- {ru} → {data['en']}" 
            for ru, data in list(self.glossary.items())[:limit]
        ]
        return "GLOSSARY (use exact translations):\n" + "\n".join(terms)


class AzureTTSSynthesizer:
    """Handles text-to-speech synthesis"""
    
    # Voice mapping by gender
    VOICES = {
        "male": {"en-US": "en-US-GuyNeural"},
        "female": {"en-US": "en-US-JennyNeural"}
    }
    
    def __init__(self, speech_key: str, region: str):
        self.speech_key = speech_key
        self.region = region
        
        # Configure Speech
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=region
        )
        
        # Default voice
        self.speech_config.speech_synthesis_voice_name = self.VOICES["female"]["en-US"]
    
    async def synthesize(
        self, 
        text: str, 
        gender: str = "female",
        language: str = "en-US"
    ) -> Optional[bytes]:
        """Synthesize text to speech audio"""
        try:
            # Select voice based on gender
            voice_name = self.VOICES.get(gender, {}).get(language)
            if not voice_name:
                voice_name = self.VOICES["female"][language]
            
            self.speech_config.speech_synthesis_voice_name = voice_name
            
            # Create synthesizer
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None  # Get raw audio data
            )
            
            # Synthesize
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"🔊 Synthesized: {len(result.audio_data)} bytes ({gender} voice)")
                return result.audio_data
            else:
                logger.error(f"TTS error: {result.reason}")
                return None
                
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None


class RealtimeTranslator:
    def __init__(self, meeting_url: str):
        self.meeting_url = meeting_url
        self.bot_id = None
        
        # Azure OpenAI for translation
        self.openai_client = AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        
        # Glossary manager
        self.glossary = GlossaryManager(GLOSSARY_PATH)
        
        # Azure TTS for synthesis
        self.azure_tts = AzureTTSSynthesizer(
            speech_key=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        
        self.web = get_web_interface()
        self.headers = {
            'Authorization': f'Token {RECALL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Speaker tracking for voice selection
        self.speakers = {}  # {speaker_name: gender}
        
        # Setup webhook endpoint
        self.setup_webhook()
    
    def setup_webhook(self):
        """Setup webhook endpoints for transcript events"""
        
        @self.web.app.post("/webhook/transcript")
        async def receive_transcript(request: Request):
            """Receive real-time transcript from Recall"""
            try:
                data = await request.json()
                event = data.get('event')
                
                if event == 'transcript.data':
                    # Final transcript
                    transcript_data = data.get('data', {}).get('data', {})
                    words = transcript_data.get('words', [])
                    text = ' '.join([w['text'] for w in words])
                    
                    participant = transcript_data.get('participant', {})
                    speaker_name = participant.get('name', 'Unknown')
                    
                    logger.info(f"💬 {speaker_name} (RU): {text}")
                    
                    # Determine gender (default female for first speaker, male for others)
                    if speaker_name not in self.speakers:
                        gender = "female" if len(self.speakers) == 0 else "male"
                        self.speakers[speaker_name] = gender
                    else:
                        gender = self.speakers[speaker_name]
                    
                    # Broadcast to web interface
                    await self.web.broadcast({
                        "type": "transcript",
                        "speaker": speaker_name,
                        "text": text,
                        "language": "ru"
                    })
                    
                    # Translate
                    translation = await self.translate(text)
                    logger.info(f"🌍 Translation (EN): {translation}")
                    
                    # Broadcast translation
                    await self.web.broadcast({
                        "type": "translation",
                        "speaker": speaker_name,
                        "original": text,
                        "translation": translation
                    })
                    
                    # Synthesize audio
                    audio_data = await self.azure_tts.synthesize(
                        text=translation,
                        gender=gender,
                        language="en-US"
                    )
                    
                    if audio_data:
                        # Send audio back to Zoom
                        await self.send_audio_to_zoom(audio_data)
                
                elif event == 'transcript.partial_data':
                    # Partial transcript (optional)
                    transcript_data = data.get('data', {}).get('data', {})
                    words = transcript_data.get('words', [])
                    text = ' '.join([w['text'] for w in words])
                    
                    participant = transcript_data.get('participant', {})
                    speaker_name = participant.get('name', 'Unknown')
                    
                    logger.debug(f"🔄 {speaker_name}: {text}")
                    
                    # Broadcast partial
                    await self.web.broadcast({
                        "type": "partial_transcript",
                        "speaker": speaker_name,
                        "text": text
                    })
                
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
                
                if event == 'bot.status_change':
                    status_data = data.get('data', {})
                    status = status_data.get('status', {}).get('code')
                    logger.info(f"Bot status: {status}")
                    
                    await self.web.broadcast({
                        "type": "system",
                        "message": f"Bot status: {status}"
                    })
                
                return {"status": "ok"}
            except Exception as e:
                logger.error(f"Bot events error: {e}")
                return {"status": "error"}
    
    async def create_bot(self):
        """Create Recall bot with transcription and bot output"""
        logger.info("🤖 Creating Recall bot with real-time transcription...")
        
        bot_data = {
            "meeting_url": self.meeting_url,
            "bot_name": "AI Translator Bot",
            "recording_config": {
                # Enable Recall transcription
                "transcript": {
                    "provider": {
                        "recallai_streaming": {
                            "language_code": "ru",
                            "filter_profanity": False,
                            "mode": "prioritize_accuracy"
                        }
                    }
                },
                # Enable real-time webhook
                "realtime_endpoints": [
                    {
                        "type": "webhook",
                        "url": f"{WEBHOOK_BASE_URL}/webhook/transcript",
                        "events": ["transcript.data", "transcript.partial_data"]
                    }
                ],
                # Enable bot audio output back to meeting
                "bot_media_output": {
                    "enabled": True,
                    "audio_enabled": True,
                    "video_enabled": False
                }
            },
            "automatic_leave": {
                "waiting_room_timeout": 1800
            }
        }
        
        response = requests.post(
            f'{BASE_URL}/bot/',
            json=bot_data,
            headers=self.headers
        )
        
        if response.status_code == 201:
            bot = response.json()
            self.bot_id = bot['id']
            logger.info(f"✅ Bot created: {self.bot_id}")
            logger.info(f"📡 Real-time transcription enabled")
            logger.info(f"🔊 Bot audio output enabled")
            
            await self.web.broadcast({
                "type": "system",
                "message": "Bot created, joining meeting..."
            })
            
            return True
        else:
            logger.error(f"❌ Failed to create bot: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    
    async def wait_for_bot_to_join(self):
        """Wait for bot to join meeting"""
        logger.info("⏳ Waiting for bot to join meeting...")
        
        max_wait = 60
        wait_interval = 2
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                response = requests.get(
                    f'{BASE_URL}/bot/{self.bot_id}',
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    bot_data = response.json()
                    status_changes = bot_data.get('status_changes', [])
                    
                    if status_changes:
                        status = status_changes[-1].get('code', '')
                        logger.info(f"📊 Bot status: {status}")
                        
                        if status in ['in_call_recording', 'in_call_not_recording']:
                            logger.info("✅ Bot joined meeting!")
                            await self.web.broadcast({
                                "type": "system",
                                "message": "Bot joined! Listening..."
                            })
                            return True
                        elif status in ['fatal', 'done']:
                            logger.error(f"❌ Bot failed: {status}")
                            return False
                            
            except Exception as e:
                logger.warning(f"Status check error: {e}")
            
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
        
        logger.error("❌ Timeout waiting for bot to join")
        return False
    
    async def translate(self, text: str) -> str:
        """Translate text using Azure OpenAI with glossary"""
        try:
            glossary_prompt = self.glossary.build_prompt()
            
            system_prompt = f"""Translate from Russian to English with high quality and natural flow.

{glossary_prompt}

Rules:
- Use glossary terms exactly as specified
- Maintain technical accuracy
- Create natural, professional English
- Preserve context and meaning
- Keep proper names unchanged
- Remove filler words (So, Well, Like, You know, I mean, Actually, Basically, etc.)
- Make text clean and professional"""

            response = await self.openai_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return "[Translation error]"
    
    async def send_audio_to_zoom(self, audio_data: bytes):
        """Send synthesized audio back to Zoom via Recall Bot Output Media"""
        try:
            # Convert audio to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Send to Recall bot output endpoint
            response = requests.post(
                f'{BASE_URL}/bot/{self.bot_id}/output_media/audio',
                json={
                    "audio": audio_base64,
                    "sample_rate": 16000,
                    "channels": 1
                },
                headers=self.headers
            )
            
            if response.status_code == 200:
                logger.info("✅ Audio sent to Zoom")
            else:
                logger.error(f"❌ Failed to send audio: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending audio to Zoom: {e}")
    
    async def start(self):
        """Start the translator bot"""
        try:
            # 1. Create bot in Recall
            if not await self.create_bot():
                logger.error("❌ Failed to create bot")
                return False
            
            # 2. Wait for bot to join meeting
            if not await self.wait_for_bot_to_join():
                logger.error("❌ Bot failed to join meeting")
                return False
            
            # 3. Bot is now listening, webhook will receive transcripts
            logger.info("✅ Translator is running!")
            logger.info("🎤 Speak in the Zoom meeting to see real-time translation")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting translator: {e}", exc_info=True)
            return False
    
    async def stop(self):
        """Stop the translator bot"""
        logger.info("🛑 Stopping translator...")
        
        # Delete bot
        if self.bot_id:
            try:
                requests.delete(
                    f'{BASE_URL}/bot/{self.bot_id}',
                    headers=self.headers
                )
                logger.info("✅ Bot deleted")
            except Exception as e:
                logger.error(f"Error deleting bot: {e}")


translator = None


async def run_translator(meeting_url: str):
    global translator
    
    translator = RealtimeTranslator(meeting_url)
    
    try:
        await translator.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        if translator:
            await translator.stop()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python realtime_translator_recall_version.py <meeting_url>")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    
    # Start web interface in background
    from app.realtime_translator.web_interface import get_web_interface
    web = get_web_interface()
    
    # Run both web server and translator
    async def main():
        # Start web server
        config = uvicorn.Config(
            web.app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Start translator
        translator_task = asyncio.create_task(run_translator(meeting_url))
        server_task = asyncio.create_task(server.serve())
        
        # Wait for both
        await asyncio.gather(translator_task, server_task)
    
    asyncio.run(main())
