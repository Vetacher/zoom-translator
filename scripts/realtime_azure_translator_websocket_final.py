#!/usr/bin/env python3

import asyncio
import logging
import sys
import os
from pathlib import Path
import requests
import json
import base64
import websockets
from contextlib import asynccontextmanager
from typing import Dict, Optional

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


class AzureSpeechTranscriber:
    """Handles real-time transcription using Azure Speech Services with speaker diarization"""
    
    def __init__(self, speech_key: str, region: str, language: str = "ru-RU"):
        self.speech_key = speech_key
        self.region = region
        self.language = language
        self.push_stream = None
        self.recognizer = None
        self.audio_config = None
        self.is_running = False
        
        # Speaker tracking
        self.speaker_info = {}  # {speaker_id: {"gender": "male/female", "name": "..."}}
        
        # Callbacks
        self.on_recognized = None
        self.on_recognizing = None
        
    def start(self):
        """Start Azure Speech recognition with speaker diarization"""
        logger.info(f"🎤 Starting Azure Speech recognition ({self.language})...")
        
        # Configure Speech
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.region
        )
        speech_config.speech_recognition_language = self.language
        
        # Enable detailed results
        speech_config.output_format = speechsdk.OutputFormat.Detailed
        
        # Configure audio format (Recall sends 16kHz, 16-bit, mono PCM)
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1
        )
        
        # Create push stream
        self.push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
        
        # Create recognizer (using standard recognizer for compatibility)
        self.recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=self.audio_config
        )
        
        # Counter for speaker tracking (since we don't have true diarization)
        self.current_speaker = "Speaker_1"
        self.speaker_counter = 1
        
        # Setup event handlers
        def recognized_handler(evt):
            """Handle final transcription"""
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = evt.result.text
                
                # Use simple speaker rotation (can be improved with voice analysis)
                speaker_id = self.current_speaker
                gender = self.get_or_infer_gender(speaker_id)
                
                logger.info(f"✅ {speaker_id} ({gender}): {text}")
                
                if self.on_recognized:
                    asyncio.create_task(self.on_recognized(
                        text=text,
                        speaker_id=speaker_id,
                        gender=gender,
                        is_final=True
                    ))
        
        def recognizing_handler(evt):
            """Handle partial transcription"""
            if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
                text = evt.result.text
                speaker_id = self.current_speaker
                
                logger.debug(f"🔄 {speaker_id}: {text}")
                
                if self.on_recognizing:
                    asyncio.create_task(self.on_recognizing(
                        text=text,
                        speaker_id=speaker_id,
                        is_final=False
                    ))
        
        def canceled_handler(evt):
            if evt.reason == speechsdk.CancellationReason.Error:
                logger.error(f"❌ Azure Speech error: {evt.error_details}")
        
        self.recognizer.recognized.connect(recognized_handler)
        self.recognizer.recognizing.connect(recognizing_handler)
        self.recognizer.canceled.connect(canceled_handler)
        
        # Start continuous recognition
        self.recognizer.start_continuous_recognition()
        self.is_running = True
        logger.info("✅ Azure Speech recognition started")
    
    def get_or_infer_gender(self, speaker_id: str) -> str:
        """Get or infer gender for speaker"""
        if speaker_id in self.speaker_info:
            return self.speaker_info[speaker_id]["gender"]
        
        # Default to female for first speaker, male for second
        # In production, you could use voice pitch analysis or manual config
        gender = "female" if len(self.speaker_info) % 2 == 0 else "male"
        self.speaker_info[speaker_id] = {"gender": gender}
        
        return gender
    
    def set_speaker_gender(self, speaker_id: str, gender: str):
        """Manually set speaker gender"""
        if speaker_id not in self.speaker_info:
            self.speaker_info[speaker_id] = {}
        self.speaker_info[speaker_id]["gender"] = gender
        logger.info(f"Set speaker {speaker_id} gender to {gender}")
    
    def write_audio(self, audio_data: bytes):
        """Write audio chunk to Azure Speech stream"""
        if self.push_stream and self.is_running:
            try:
                self.push_stream.write(audio_data)
            except Exception as e:
                logger.error(f"Error writing audio to Azure: {e}")
    
    def stop(self):
        """Stop Azure Speech recognition"""
        if self.recognizer and self.is_running:
            logger.info("🛑 Stopping Azure Speech recognition...")
            self.recognizer.stop_continuous_recognition()
            self.is_running = False
        
        if self.push_stream:
            self.push_stream.close()
            
        logger.info("✅ Azure Speech recognition stopped")


class AzureTTSSynthesizer:
    """Handles text-to-speech synthesis with gender-specific voices"""
    
    # Voice mapping by gender
    VOICES = {
        "male": {
            "en-US": "en-US-GuyNeural",  # Natural male voice
            "ru-RU": "ru-RU-DmitryNeural"
        },
        "female": {
            "en-US": "en-US-JennyNeural",  # Natural female voice
            "ru-RU": "ru-RU-SvetlanaNeural"
        }
    }
    
    def __init__(self, speech_key: str, region: str):
        self.speech_key = speech_key
        self.region = region
        
        # Configure Speech
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=region
        )
        
        # Use neural voices for better quality
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
            
            # Configure audio output to memory stream
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None  # Get raw audio data
            )
            
            # Synthesize
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"🔊 Synthesized audio: {len(result.audio_data)} bytes ({gender} voice)")
                return result.audio_data
            else:
                logger.error(f"TTS error: {result.reason}")
                return None
                
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None


class RecallWebSocketClient:
    """Handles WebSocket connection to Recall.ai for audio streaming"""
    
    def __init__(self, bot_id: str, api_key: str):
        self.bot_id = bot_id
        self.api_key = api_key
        self.ws = None
        self.is_connected = False
        
        # Callbacks
        self.on_audio = None
        self.on_transcript = None
        
    async def connect(self):
        """Connect to Recall WebSocket"""
        ws_url = f"wss://us-west-2.recall.ai/api/v1/bot/{self.bot_id}/real-time"
        
        logger.info(f"🔌 Connecting to Recall WebSocket: {ws_url}")
        
        try:
            self.ws = await websockets.connect(
                ws_url,
                additional_headers={
                    "Authorization": f"Token {self.api_key}"
                }
            )
            self.is_connected = True
            logger.info("✅ Connected to Recall WebSocket")
            
            # Subscribe to audio events
            await self.subscribe_to_audio()
            
            # Start receiving messages
            await self.receive_messages()
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            self.is_connected = False
    
    async def subscribe_to_audio(self):
        """Subscribe to audio stream"""
        subscribe_message = {
            "type": "subscribe",
            "events": ["audio", "transcript"]
        }
        await self.ws.send(json.dumps(subscribe_message))
        logger.info("📡 Subscribed to audio stream")
    
    async def receive_messages(self):
        """Receive and process WebSocket messages"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self.is_connected = False
    
    async def handle_message(self, data: dict):
        """Handle incoming WebSocket message"""
        event_type = data.get('event')
        
        if event_type == 'audio':
            # Audio data received
            audio_data = data.get('data', {})
            await self.handle_audio(audio_data)
            
        elif event_type == 'transcript':
            # Transcript data (optional, for fallback)
            transcript_data = data.get('data', {})
            if self.on_transcript:
                await self.on_transcript(transcript_data)
    
    async def handle_audio(self, audio_data: dict):
        """Handle audio data"""
        try:
            # Audio data is base64 encoded PCM
            audio_base64 = audio_data.get('audio')
            if not audio_base64:
                return
            
            # Decode from base64
            raw_audio = base64.b64decode(audio_base64)
            
            # Get participant info
            participant_id = audio_data.get('participant_id')
            
            logger.debug(f"🎵 Received audio chunk: {len(raw_audio)} bytes from participant {participant_id}")
            
            # Send to callback (Azure Speech)
            if self.on_audio:
                await self.on_audio(raw_audio, participant_id)
                
        except Exception as e:
            logger.error(f"Error handling audio: {e}")
    
    async def close(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("WebSocket closed")


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
        
        # Azure Speech for transcription
        self.azure_speech = AzureSpeechTranscriber(
            speech_key=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION,
            language="ru-RU"
        )
        
        # Azure TTS for synthesis
        self.azure_tts = AzureTTSSynthesizer(
            speech_key=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        
        # Recall WebSocket client
        self.ws_client = None
        
        self.web = get_web_interface()
        self.headers = {
            'Authorization': f'Token {RECALL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Setup callbacks
        self.setup_azure_callbacks()
        
        # Setup webhook endpoint (for bot status events)
        self.setup_webhook()
    
    def setup_azure_callbacks(self):
        """Setup callbacks for Azure Speech recognition"""
        
        async def on_recognized(text: str, speaker_id: str, gender: str, is_final: bool):
            """Handle final recognized text from Azure"""
            logger.info(f"💬 Final transcript [{speaker_id}, {gender}]: {text}")
            
            # Translate with glossary and filtering
            translation = await self.translate(text)
            logger.info(f"🌍 Translation: {translation}")
            
            # Broadcast to web interface
            await self.web.broadcast({
                "type": "translation",
                "speaker": f"Speaker {speaker_id}",
                "speaker_id": speaker_id,
                "gender": gender,
                "original": text,
                "translation": translation
            })
            
            # Synthesize audio with appropriate voice
            audio_data = await self.azure_tts.synthesize(
                text=translation,
                gender=gender,
                language="en-US"
            )
            
            if audio_data:
                # Send audio back to Zoom via Recall
                await self.send_audio_to_zoom(audio_data)
        
        async def on_recognizing(text: str, speaker_id: str, is_final: bool):
            """Handle partial recognized text from Azure"""
            logger.debug(f"🔄 Partial transcript [{speaker_id}]: {text}")
            
            # Broadcast partial result
            await self.web.broadcast({
                "type": "partial_transcript",
                "speaker": f"Speaker {speaker_id}",
                "speaker_id": speaker_id,
                "text": text
            })
        
        self.azure_speech.on_recognized = on_recognized
        self.azure_speech.on_recognizing = on_recognizing
    
    def setup_webhook(self):
        """Setup webhook endpoints for bot status events"""
        
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
                
                return {"status": "ok"}
            except Exception as e:
                logger.error(f"Bot events error: {e}")
                return {"status": "error"}
    
    async def create_bot(self):
        """Create Recall bot with WebSocket audio streaming and bot output"""
        logger.info("🤖 Creating Recall bot with WebSocket audio streaming...")
        
        bot_data = {
            "meeting_url": self.meeting_url,
            "bot_name": "AI Translator Bot",
            "recording_config": {
                # Enable real-time audio INPUT via WebSocket
                "real_time_media": {
                    "websocket_audio_output_enabled": True,
                },
                # Enable bot audio OUTPUT back to meeting
                "bot_media_output": {
                    "enabled": True,
                    "audio_enabled": True,
                    "video_enabled": False
                }
            },
            # Optional: webhook for bot status events
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
            logger.info(f"📡 WebSocket audio streaming enabled")
            logger.info(f"🔊 Bot audio output enabled")
            
            await self.web.broadcast({
                "type": "system",
                "message": "Bot connected, starting audio capture..."
            })
            
            return True
        else:
            logger.error(f"❌ Failed to create bot: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    
    async def connect_websocket(self):
        """Connect to Recall WebSocket for audio streaming"""
        if not self.bot_id:
            logger.error("Cannot connect WebSocket: bot_id is None")
            return False
        
        # Create WebSocket client
        self.ws_client = RecallWebSocketClient(
            bot_id=self.bot_id,
            api_key=RECALL_API_KEY
        )
        
        # Setup callback to send audio to Azure
        async def on_audio(audio_data: bytes, participant_id: str):
            """Send audio to Azure Speech"""
            self.azure_speech.write_audio(audio_data)
        
        self.ws_client.on_audio = on_audio
        
        # Connect (this will block until connection is closed)
        try:
            await self.ws_client.connect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            return False
        
        return True
    
    async def translate(self, text: str) -> str:
        """Translate text using Azure OpenAI with glossary and filtering"""
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
            return f"[Translation error]"
    
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
                    "sample_rate": 16000,  # Azure TTS default
                    "channels": 1
                },
                headers=self.headers
            )
            
            if response.status_code == 200:
                logger.info("✅ Audio sent to Zoom successfully")
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
            
            # 2. Wait for bot to join meeting (WebSocket becomes available after bot joins)
            logger.info("⏳ Waiting for bot to join meeting...")
            await self.web.broadcast({
                "type": "system",
                "message": "Waiting for bot to join meeting..."
            })
            
            # Poll bot status
            max_wait = 60  # 60 seconds max
            wait_interval = 2  # check every 2 seconds
            elapsed = 0
            
            while elapsed < max_wait:
                try:
                    response = requests.get(
                        f'{BASE_URL}/bot/{self.bot_id}',
                        headers=self.headers
                    )
                    
                    if response.status_code == 200:
                        bot_data = response.json()
                        status = bot_data.get('status_changes', [{}])[-1].get('code', '')
                        
                        logger.info(f"📊 Bot status: {status}")
                        
                        if status == 'in_call_not_recording':
                            logger.info("✅ Bot joined meeting!")
                            await self.web.broadcast({
                                "type": "system",
                                "message": "Bot joined meeting!"
                            })
                            break
                        elif status in ['fatal', 'done']:
                            logger.error(f"❌ Bot failed to join: {status}")
                            return False
                            
                except Exception as e:
                    logger.warning(f"Status check error: {e}")
                
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval
            
            if elapsed >= max_wait:
                logger.error("❌ Timeout waiting for bot to join")
                return False
            
            # 3. Start Azure Speech recognition
            self.azure_speech.start()
            
            # 4. Connect to Recall WebSocket for audio streaming
            logger.info("🔌 Connecting to Recall WebSocket...")
            await self.web.broadcast({
                "type": "system",
                "message": "Connecting to audio stream..."
            })
            
            # This will block until connection closes
            await self.connect_websocket()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting translator: {e}", exc_info=True)
            return False
    
    async def stop(self):
        """Stop the translator bot"""
        logger.info("🛑 Stopping translator...")
        
        # Stop Azure Speech
        self.azure_speech.stop()
        
        # Close WebSocket
        if self.ws_client:
            await self.ws_client.close()
        
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    # Startup
    yield
    # Shutdown
    if translator:
        await translator.stop()


def create_app():
    """Create FastAPI app"""
    from app.realtime_translator.web_interface import get_web_interface
    web = get_web_interface()
    web.app.router.lifespan_context = lifespan
    return web.app


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python realtime_azure_translator_websocket_final.py <meeting_url>")
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
