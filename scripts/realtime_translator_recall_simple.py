#!/usr/bin/env python3
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from openai import AsyncAzureOpenAI
import os
import subprocess
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
        <title>AI Real-Time Translator</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body { 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            header {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }
            
            h1 { 
                font-size: 2.5em;
                font-weight: 700;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }
            
            .subtitle {
                color: #666;
                font-size: 1.1em;
                font-weight: 400;
            }
            
            .status {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 20px 30px;
                border-radius: 15px;
                margin-bottom: 30px;
                display: flex;
                align-items: center;
                gap: 15px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                font-weight: 500;
            }
            
            .status-indicator {
                width: 12px;
                height: 12px;
                background: #4CAF50;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            #translations {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            
            .translation { 
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 25px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                animation: slideIn 0.3s ease-out;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .translation:hover {
                transform: translateY(-2px);
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .translation-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 2px solid #f0f0f0;
            }
            
            .speaker {
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 600;
                color: #333;
                font-size: 1.1em;
            }
            
            .speaker-icon {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 1.2em;
            }
            
            .timestamp {
                color: #999;
                font-size: 0.9em;
                font-weight: 500;
            }
            
            .text-block {
                margin-bottom: 15px;
            }
            
            .language-label {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.75em;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }
            
            .ru-label {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                color: white;
            }
            
            .en-label {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            .text-content {
                font-size: 1.05em;
                line-height: 1.6;
                color: #333;
            }
            
            .ru-text {
                color: #2d3748;
            }
            
            .en-text {
                color: #4a5568;
            }
            
            audio { 
                width: 100%;
                height: 45px;
                border-radius: 25px;
                margin-top: 15px;
                outline: none;
            }
            
            audio::-webkit-media-controls-panel {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 25px;
            }
            
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: white;
            }
            
            .empty-state-icon {
                font-size: 4em;
                margin-bottom: 20px;
                opacity: 0.8;
            }
            
            .empty-state-text {
                font-size: 1.3em;
                font-weight: 500;
            }
            
            @media (max-width: 768px) {
                h1 { font-size: 1.8em; }
                .subtitle { font-size: 1em; }
                .translation { padding: 20px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🌍 AI Real-Time Translator</h1>
                <div class="subtitle">Russian → English • Powered by Azure AI</div>
            </header>
            
            <div class="status" id="status">
                <div class="status-indicator"></div>
                <span>Connecting...</span>
            </div>
            
            <div id="translations"></div>
            
            <div id="empty-state" class="empty-state">
                <div class="empty-state-icon">🎤</div>
                <div class="empty-state-text">Waiting for translations...</div>
            </div>
        </div>
        
        <script>
            async function updateTranslations() {
                try {
                    const res = await fetch('/translations');
                    const data = await res.json();
                    
                    document.getElementById('status').innerHTML = 
                        `<div class="status-indicator"></div><span>✅ Live • ${data.length} translation${data.length !== 1 ? 's' : ''}</span>`;
                    
                    if (data.length === 0) {
                        document.getElementById('empty-state').style.display = 'block';
                        document.getElementById('translations').innerHTML = '';
                        return;
                    }
                    
                    document.getElementById('empty-state').style.display = 'none';
                    
                    document.getElementById('translations').innerHTML = data.map(t => `
                        <div class="translation">
                            <div class="translation-header">
                                <div class="speaker">
                                    <div class="speaker-icon">🎤</div>
                                    <span>${t.speaker}</span>
                                </div>
                                <div class="timestamp">${t.timestamp}</div>
                            </div>
                            
                            <div class="text-block">
                                <span class="language-label ru-label">🇷🇺 Russian</span>
                                <div class="text-content ru-text">${t.original}</div>
                            </div>
                            
                            <div class="text-block">
                                <span class="language-label en-label">🇬🇧 English</span>
                                <div class="text-content en-text">${t.translation}</div>
                            </div>
                            
                            <audio controls src="/audio/${t.id}.wav" preload="none"></audio>
                        </div>
                    `).reverse().join('');
                } catch(e) {
                    document.getElementById('status').innerHTML = 
                        '<div style="width: 12px; height: 12px; background: #f44336; border-radius: 50%;"></div><span>❌ Connection error: ' + e.message + '</span>';
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
                # Save raw audio first
                raw_path = f"/tmp/{audio_id}_raw.wav"
                with open(raw_path, 'wb') as f:
                    f.write(audio_data)
                
                # Convert to browser-compatible WAV using ffmpeg
                import subprocess
                result = subprocess.run(
                    ['ffmpeg', '-i', raw_path, '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', '-y', audio_path],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"🔊 Audio saved and converted: {audio_path}")
                    # Remove raw file
                    os.remove(raw_path)
                else:
                    print(f"⚠️ FFmpeg conversion failed, using raw audio")
                    os.rename(raw_path, audio_path)
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
