#!/usr/bin/env python3
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from openai import AsyncAzureOpenAI
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import azure.cognitiveservices.speech as speechsdk
from datetime import datetime

load_dotenv()

# Glossary
glossary_path = Path("config/translation_glossary.json")
glossary = {}
if glossary_path.exists():
    with open(glossary_path, 'r', encoding='utf-8') as f:
        glossary = json.load(f)
    print(f"Loaded {len(glossary)} glossary terms")

def build_glossary_prompt():
    if not glossary:
        return ""
    terms = [f"- {ru} → {data['en']}" for ru, data in list(glossary.items())[:30]]
    return "GLOSSARY:\n" + "\n".join(terms)

# Azure clients
openai_client = AsyncAzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv('AZURE_SPEECH_KEY'),
    region=os.getenv('AZURE_SPEECH_REGION', 'westeurope')
)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

app = FastAPI()

# Store translations for web display
translations = []

async def translate(text: str) -> str:
    glossary_prompt = build_glossary_prompt()
    response = await openai_client.chat.completions.create(
        model=os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY'),
        messages=[
            {
                "role": "system", 
                "content": f"Translate Russian to English naturally. Remove filler words (So, Well, Like, You know, I mean).\n\n{glossary_prompt}"
            },
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return response.choices[0].message.content.strip()

def synthesize_audio(text: str) -> bytes:
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    return None

@app.get("/", response_class=HTMLResponse)
async def root():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real-Time Translator</title>
        <meta charset="UTF-8">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                padding: 20px; 
                background: #1a1a1a; 
                color: #fff; 
                max-width: 1200px;
                margin: 0 auto;
            }
            h1 { color: #4CAF50; }
            .translation { 
                margin: 20px 0; 
                padding: 20px; 
                background: #2a2a2a; 
                border-radius: 8px;
                border-left: 4px solid #4CAF50;
            }
            .ru { 
                color: #4CAF50; 
                font-size: 18px;
                margin-bottom: 10px;
            }
            .en { 
                color: #2196F3; 
                font-size: 18px;
                margin-bottom: 10px;
            }
            .timestamp {
                color: #888;
                font-size: 12px;
            }
            audio { 
                width: 100%; 
                margin-top: 10px;
            }
            .status {
                padding: 10px;
                background: #333;
                border-radius: 4px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <h1>🌍 Real-Time Translator</h1>
        <div class="status" id="status">Loading...</div>
        <div id="translations"></div>
        
        <script>
            async function updateTranslations() {
                try {
                    const res = await fetch('/translations');
                    const data = await res.json();
                    
                    document.getElementById('status').innerHTML = 
                        `✅ Connected | ${data.length} translations`;
                    
                    document.getElementById('translations').innerHTML = data.map(t => `
                        <div class="translation">
                            <div class="timestamp">${t.timestamp}</div>
                            <div class="ru">🎤 ${t.speaker}: ${t.original}</div>
                            <div class="en">🌍 Translation: ${t.translation}</div>
                            <audio controls src="/audio/${t.id}.wav" preload="none"></audio>
                        </div>
                    `).reverse().join('');
                } catch(e) {
                    document.getElementById('status').innerHTML = '❌ Error: ' + e.message;
                }
            }
            
            // Update every 2 seconds
            setInterval(updateTranslations, 2000);
            updateTranslations();
        </script>
    </body>
    </html>
    """
    return html

@app.get("/translations")
async def get_translations():
    return translations[-20:]  # Last 20 translations

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(f"/tmp/{filename}")
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/wav")
    return {"error": "Audio file not found"}

@app.post("/webhook/transcript")
async def receive_transcript(request: Request):
    try:
        data = await request.json()
        event = data.get('event')
        
        if event == 'transcript.data':
            transcript_data = data.get('data', {}).get('data', {})
            words = transcript_data.get('words', [])
            text = ' '.join([w['text'] for w in words])
            
            participant = transcript_data.get('participant', {})
            speaker = participant.get('name', 'Unknown')
            
            print(f"\n{'='*70}")
            print(f"🎤 {speaker}: {text}")
            
            # Translate
            translation = await translate(text)
            print(f"🌍 EN: {translation}")
            
            # Synthesize audio
            audio_data = synthesize_audio(translation)
            
            # Save audio file
            timestamp = datetime.now().strftime("%H:%M:%S")
            audio_id = f"trans_{datetime.now().strftime('%H%M%S_%f')}"
            audio_path = f"/tmp/{audio_id}.wav"
            
            if audio_data:
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)
                print(f"🔊 Audio saved: {audio_path}")
            else:
                print("⚠️ No audio generated")
            
            # Store for web display
            translations.append({
                "id": audio_id,
                "speaker": speaker,
                "original": text,
                "translation": translation,
                "timestamp": timestamp
            })
            
            print(f"{'='*70}\n")
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("Starting Real-Time Translator...")
    print("Web interface: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
