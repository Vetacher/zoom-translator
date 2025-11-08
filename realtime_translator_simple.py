#!/usr/bin/env python3
from fastapi import FastAPI
import uvicorn
from openai import AsyncAzureOpenAI
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import azure.cognitiveservices.speech as speechsdk
import base64
from datetime import datetime

load_dotenv()

# Glossary
glossary_path = Path("config/translation_glossary.json")
glossary = {}
if glossary_path.exists():
    with open(glossary_path, 'r', encoding='utf-8') as f:
        glossary = json.load(f)

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
    region=os.getenv('AZURE_SPEECH_REGION')
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
            {"role": "system", "content": f"Translate Russian to English. Remove filler words.\n\n{glossary_prompt}"},
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

@app.get("/")
async def root():
    html = """
    <html>
    <head><title>Real-Time Translator</title>
    <style>
        body { font-family: Arial; padding: 20px; background: #1a1a1a; color: #fff; }
        .translation { margin: 20px 0; padding: 15px; background: #2a2a2a; border-radius: 8px; }
        .ru { color: #4CAF50; }
        .en { color: #2196F3; }
        audio { width: 100%; margin-top: 10px; }
    </style>
    </head>
    <body>
        <h1>🌍 Real-Time Translator</h1>
        <div id="translations"></div>
        <script>
            setInterval(async () => {
                const res = await fetch('/translations');
                const data = await res.json();
                document.getElementById('translations').innerHTML = data.map(t => `
                    <div class="translation">
                        <div class="ru">🎤 ${t.speaker}: ${t.original}</div>
                        <div class="en">🌍 EN: ${t.translation}</div>
                        <audio controls src="/audio/${t.id}.wav"></audio>
                    </div>
                `).reverse().join('');
            }, 2000);
        </script>
    </body>
    </html>
    """
    return {"message": html}

@app.get("/translations")
async def get_translations():
    return translations[-10:]  # Last 10

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(f"/tmp/{filename}")
    if audio_path.exists():
        with open(audio_path, 'rb') as f:
            return f.read()
    return {"error": "not found"}

@app.post("/webhook/transcript")
async def receive_transcript(request):
    data = await request.json()
    if data.get('event') == 'transcript.data':
        transcript_data = data.get('data', {}).get('data', {})
        words = transcript_data.get('words', [])
        text = ' '.join([w['text'] for w in words])
        speaker = transcript_data.get('participant', {}).get('name', 'Unknown')
        
        print(f"\n{'='*70}")
        print(f"🎤 {speaker}: {text}")
        
        # Translate
        translation = await translate(text)
        print(f"🌍 EN: {translation}")
        
        # Synthesize
        audio_data = synthesize_audio(translation)
        
        # Save audio file
        timestamp = datetime.now().strftime("%H%M%S")
        audio_id = f"trans_{timestamp}"
        audio_path = f"/tmp/{audio_id}.wav"
        
        if audio_data:
            # Convert to WAV format
            with open(audio_path, 'wb') as f:
                f.write(audio_data)
            print(f"🔊 Audio saved: {audio_path}")
        
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
