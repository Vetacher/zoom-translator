#!/usr/bin/env python3

import asyncio
import logging
import sys
import os
from pathlib import Path
import requests
import websockets
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import uvicorn

from app.realtime_translator.web_interface import get_web_interface

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv('RECALL_API_KEY')
BASE_URL = 'https://us-west-2.recall.ai/api/v1'
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY')
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

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
            'Authorization': f'Token {API_KEY}',
            'Content-Type': 'application/json'
        }
    
    async def create_bot(self):
        logger.info("Creating Recall bot...")
        
        bot_data = {
            "meeting_url": self.meeting_url,
            "bot_name": "AI Translator Bot"
        }
        
        response = requests.post(
            f'{BASE_URL}/bot',
            json=bot_data,
            headers=self.headers
        )
        
        if response.status_code == 201:
            bot = response.json()
            self.bot_id = bot['id']
            logger.info(f"✓ Bot created: {self.bot_id}")
            
            await self.web.broadcast({
                "type": "system",
                "message": f"Bot connected to meeting"
            })
            
            return True
        else:
            logger.error(f"Failed to create bot: {response.text}")
            return False
    
    async def connect_websocket(self):
        ws_url = f"wss://us-west-2.recall.ai/api/v1/bot/{self.bot_id}/transcript"
        
        logger.info("Connecting to transcript WebSocket...")
        
        try:
            async with websockets.connect(
                ws_url,
                additional_headers={"Authorization": f"Token {API_KEY}"}
            ) as websocket:
                logger.info("✓ WebSocket connected, waiting for transcripts...")
                
                await self.web.broadcast({
                    "type": "system",
                    "message": "Listening to meeting..."
                })
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_transcript(data)
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    async def handle_transcript(self, data: dict):
        try:
            speaker = data.get('speaker', 'Unknown')
            text = data.get('words', '').strip()
            
            if not text:
                return
            
            logger.info(f"{speaker}: {text}")
            
            translation = await self.translate(text)
            logger.info(f"→ {translation}")
            
            await self.web.broadcast({
                "type": "translation",
                "speaker": speaker,
                "original": text,
                "translation": translation
            })
            
            await self.send_to_zoom_chat(f"[{speaker}] {translation}")
        
        except Exception as e:
            logger.error(f"Error in handle_transcript: {e}")
    
    async def translate(self, text: str) -> str:
        try:
            response = await self.openai_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate Russian to English. Provide only the translation, no explanations."
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
    
    async def send_to_zoom_chat(self, message: str):
        try:
            response = requests.post(
                f'{BASE_URL}/bot/{self.bot_id}/send_chat_message',
                json={"message": message},
                headers=self.headers
            )
            if response.status_code != 200:
                logger.error(f"Failed to send chat: {response.text}")
        except Exception as e:
            logger.error(f"Error sending to Zoom: {e}")
    
    async def start(self):
        try:
            if not await self.create_bot():
                return
            
            await self.connect_websocket()
        
        except Exception as e:
            logger.error(f"Error in start: {e}")
    
    async def stop(self):
        if self.bot_id:
            try:
                response = requests.delete(
                    f'{BASE_URL}/bot/{self.bot_id}',
                    headers=self.headers
                )
                logger.info("✓ Bot deleted")
            except Exception as e:
                logger.error(f"Error deleting bot: {e}")

translator = None

async def run_translator(meeting_url: str):
    global translator
    translator = RealtimeTranslator(meeting_url)
    await translator.start()

def main():
    if len(sys.argv) < 2:
        print("❌ No meeting URL provided!")
        print("\nUsage:")
        print("  python3 scripts/realtime_web_translator.py <ZOOM_URL>")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    
    if not API_KEY:
        print("❌ RECALL_API_KEY not found in .env")
        sys.exit(1)
    
    if not AZURE_OPENAI_KEY:
        print("❌ AZURE_OPENAI_KEY not found in .env")
        sys.exit(1)
    
    if not AZURE_OPENAI_ENDPOINT:
        print("❌ AZURE_OPENAI_ENDPOINT not found in .env")
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("🌐 Zoom Real-Time Translator")
    logger.info("="*60)
    logger.info(f"📹 Meeting: {meeting_url}")
    logger.info(f"🔑 Recall API: {'✓' if API_KEY else '✗'}")
    logger.info(f"🤖 Azure OpenAI: {'✓' if AZURE_OPENAI_KEY else '✗'}")
    logger.info(f"📦 Deployment: {AZURE_OPENAI_DEPLOYMENT}")
    logger.info("="*60)
    
    web = get_web_interface()
    
    @web.app.on_event("startup")
    async def startup():
        asyncio.create_task(run_translator(meeting_url))
    
    @web.app.on_event("shutdown")
    async def shutdown():
        if translator:
            await translator.stop()
    
    port = int(os.getenv('WEB_PORT', 8000))
    
    logger.info(f"🌐 Web interface: http://172.205.192.158:{port}")
    logger.info("="*60)
    logger.info("Press Ctrl+C to stop")
    logger.info("="*60 + "\n")
    
    uvicorn.run(web.app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
