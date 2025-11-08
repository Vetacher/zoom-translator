#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path
import requests
import json
import base64
import subprocess
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse

# Azure Speech SDK
import azure.cognitiveservices.speech as speechsdk

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
WEBSOCKET_BASE_URL = os.getenv('WEBSOCKET_URL', 'wss://zoom-bot-vm.westeurope.cloudapp.azure.com')

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
    """Handles real-time transcription using Azure Speech Services"""
    
    def __init__(self, speech_key: str, region: str, language: str = "ru-RU"):
        self.speech_key = speech_key
        self.region = region
        self.language = language
        self.push_stream = None
        self.recognizer = None
        self.audio_config = None
        self.is_running = False
        
        # Callbacks
        self.on_recognized = None
        self.on_recognizing = None
        
    def start(self):
        """Start Azure Speech recognition"""
        logger.info(f"🎤 Starting Azure Speech recognition ({self.language})...")
        
        # Configure Speech
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.region
        )
        speech_config.speech_recognition_language = self.language
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
        
        # Create recognizer
        self.recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=self.audio_config
        )
        
        # Setup event handlers
        def recognized_handler(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                logger.info(f"✅ Azure recognized: {evt.result.text}")
                if self.on_recognized:
                    asyncio.create_task(self.on_recognized(evt.result.text, is_final=True))
        
        def recognizing_handler(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
                logger.debug(f"🔄 Azure recognizing: {evt.result.text}")
                if self.on_recognizing:
                    asyncio.create_task(self.on_recognizing(evt.result.text, is_final=False))
        
        def canceled_handler(evt):
            if evt.reason == speechsdk.CancellationReason.Error:
                logger.error(f"❌ Azure Speech error: {evt.error_details}")
        
        self.recognizer.recognized.connect(recognized_handler)
        
        def session_started(evt):
            logger.info("🎙️ Azure Speech session started")
        
        def session_stopped(evt):
            logger.info("🛑 Azure Speech session stopped")
        
        self.recognizer.session_started.connect(session_started)
        self.recognizer.session_stopped.connect(session_stopped)
        self.recognizer.recognizing.connect(recognizing_handler)
        self.recognizer.canceled.connect(canceled_handler)
        
        # Start continuous recognition
        self.recognizer.start_continuous_recognition()
        self.is_running = True
        logger.info("✅ Azure Speech recognition started")
    def write_audio(self, audio_data: bytes):
        """Write audio chunk to Azure Speech stream"""
        if not self.push_stream:
            logger.warning("⚠️ push_stream is None!")
            return
        if not self.is_running:
            logger.warning("⚠️ is_running is False!")
            return
            
        try:
            self.push_stream.write(audio_data)
            logger.debug(f"✍️ Wrote {len(audio_data)} bytes to Azure")
        except Exception as e:
            logger.error(f"❌ Error writing audio to Azure: {e}")

    
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
    """Handles text-to-speech synthesis"""
    
    VOICES = {
        "male": {"en-US": "en-US-GuyNeural"},
        "female": {"en-US": "en-US-JennyNeural"}
    }
    
    def __init__(self, speech_key: str, region: str):
        self.speech_key = speech_key
        self.region = region
        
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=region
        )
        self.speech_config.speech_synthesis_voice_name = self.VOICES["female"]["en-US"]
    
    async def synthesize(
        self, 
        text: str, 
        gender: str = "female",
        language: str = "en-US"
    ) -> Optional[bytes]:
        """Synthesize text to speech audio"""
        try:
            voice_name = self.VOICES.get(gender, {}).get(language)
            if not voice_name:
                voice_name = self.VOICES["female"][language]
            
            self.speech_config.speech_synthesis_voice_name = voice_name
            
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None
            )
            
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
        
        self.app = FastAPI()
        self.headers = {
            'Authorization': f'Token {RECALL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Storage
        self.translations = []
        self.speakers = {}
        
        # Setup callbacks and routes
        self.setup_azure_callbacks()
        self.setup_routes()
    
    def setup_azure_callbacks(self):
        """Setup callbacks for Azure Speech recognition"""
        
        async def on_recognized(text: str, is_final: bool):
            """Handle final recognized text from Azure"""
            logger.info(f"💬 Final transcript: {text}")
            
            # Translate
            translation = await self.translate(text)
            logger.info(f"🌍 Translation: {translation}")
            
            # Synthesize audio
            audio_data = await self.azure_tts.synthesize(
                text=translation,
                gender="female",
                language="en-US"
            )
            
            # Save audio
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            audio_id = f"trans_{datetime.now().strftime('%H%M%S_%f')}"
            audio_path = f"/tmp/{audio_id}.wav"
            
            if audio_data:
                # Save raw audio first
                raw_path = f"/tmp/{audio_id}_raw.wav"
                with open(raw_path, 'wb') as f:
                    f.write(audio_data)
                
                # Convert to browser-compatible WAV
                result = subprocess.run(
                    ['ffmpeg', '-i', raw_path, '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', '-y', audio_path],
                    capture_output=True
                )
                
                if result.returncode == 0:
                    logger.info(f"🔊 Audio saved: {audio_path}")
                    os.remove(raw_path)
                else:
                    logger.warning(f"⚠️ FFmpeg conversion failed, using raw audio")
                    os.rename(raw_path, audio_path)
            
            # Store translation
            self.translations.append({
                "id": audio_id,
                "speaker": "Participant",
                "original": text,
                "translation": translation,
                "timestamp": timestamp
            })
        
        async def on_recognizing(text: str, is_final: bool):
            """Handle partial recognized text from Azure"""
            logger.debug(f"🔄 Partial transcript: {text}")
        
        self.azure_speech.on_recognized = on_recognized
        self.azure_speech.on_recognizing = on_recognizing
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.websocket("/ws/audio")
        async def websocket_audio_endpoint(websocket: WebSocket):
            """WebSocket endpoint for receiving audio from Recall"""
            await websocket.accept()
            logger.info("🔌 Recall connected to WebSocket")
            
            try:
                while True:
                    data = await websocket.receive_json()
                    
                    event = data.get('event')
                    if event == 'audio_separate_raw.data':
                        event_data = data.get('data', {}).get('data', {})
                        
                        # Get audio buffer (base64 encoded)
                        audio_base64 = event_data.get('buffer')
                        if not audio_base64:
                            continue
                        
                        # Decode audio
                        audio_bytes = base64.b64decode(audio_base64)
                        
                        # Get participant info
                        participant = event_data.get('participant', {})
                        participant_name = participant.get('name', 'Unknown')
                        
                        logger.info(f"🎵 Received audio: {len(audio_bytes)} bytes from {participant_name}")
                        
                        # Send to Azure Speech
                        self.azure_speech.write_audio(audio_bytes)
                        
            except WebSocketDisconnect:
                logger.info("🔌 Recall disconnected from WebSocket")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Web interface"""
            with open(Path(__file__).parent / "web_template.html", 'r') as f:
                return f.read()
        
        @self.app.get("/translations")
        async def get_translations():
            """Get recent translations"""
            return self.translations[-20:]
        
        @self.app.get("/audio/{filename}")
        async def get_audio(filename: str):
            """Serve audio file"""
            audio_path = Path(f"/tmp/{filename}")
            if audio_path.exists():
                return FileResponse(audio_path, media_type="audio/wav")
            return {"error": "Audio file not found"}
    
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
    
    async def create_bot(self):
        """Create Recall bot with WebSocket audio streaming"""
        logger.info("🤖 Creating Recall bot with WebSocket audio streaming...")
        
        bot_data = {
            "meeting_url": self.meeting_url,
            "bot_name": "AI Translator Bot",
            "recording_config": {
                # Enable separate audio streams
                "audio_separate_raw": {},
                # WebSocket endpoint for real-time audio
                "realtime_endpoints": [
                    {
                        "type": "websocket",
                        "url": f"wss://zoom-bot-vm.westeurope.cloudapp.azure.com/ws/audio",
                        "events": ["audio_separate_raw.data"]
                    }
                ]
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
            logger.info(f"🔊 WebSocket audio streaming enabled")
            return True
        else:
            logger.error(f"❌ Failed to create bot: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    
    async def start(self):
        """Start the translator bot"""
        try:
            # 1. Create bot in Recall
            if not await self.create_bot():
                logger.error("❌ Failed to create bot")
                return False
            
            # 2. Start Azure Speech recognition
            self.azure_speech.start()
            
            # 3. WebSocket server is ready, waiting for Recall to connect
            logger.info("✅ Translator is running!")
            logger.info("🎤 Waiting for Recall to connect and stream audio...")
            logger.info(f"📡 WebSocket endpoint: {WEBHOOK_BASE_URL}/ws/audio")
            
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
        
        # Stop Azure Speech
        self.azure_speech.stop()
        
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
        print("Usage: python realtime_translator_websocket_audio.py <meeting_url>")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    
    translator = RealtimeTranslator(meeting_url)
    
    # Run both web server and translator
    async def main():
        # Start web server
        config = uvicorn.Config(
            translator.app,
            host="0.0.0.0",
            port=8001,  # Different port
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Start translator
        translator_task = asyncio.create_task(run_translator(meeting_url))
        server_task = asyncio.create_task(server.serve())
        
        # Wait for both
        await asyncio.gather(translator_task, server_task)
    
    asyncio.run(main())
