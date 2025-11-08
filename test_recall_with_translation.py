#!/usr/bin/env python3
from fastapi import FastAPI, Request
import uvicorn
import logging
from openai import AsyncAzureOpenAI
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load glossary
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

client = AsyncAzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

app = FastAPI()

async def translate(text: str) -> str:
    glossary_prompt = build_glossary_prompt()
    response = await client.chat.completions.create(
        model=os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY'),
        messages=[
            {"role": "system", "content": f"Translate Russian to English. Use glossary terms exactly. Remove filler words.\n\n{glossary_prompt}"},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return response.choices[0].message.content.strip()

@app.post("/webhook/transcript")
async def receive_transcript(request: Request):
    data = await request.json()
    event = data.get('event')
    
    if event == 'transcript.data':
        transcript_data = data.get('data', {}).get('data', {})
        words = transcript_data.get('words', [])
        text = ' '.join([w['text'] for w in words])
        speaker = transcript_data.get('participant', {}).get('name', 'Unknown')
        
        print(f"\n{'='*70}")
        print(f"🎤 {speaker}: {text}")
        translation = await translate(text)
        print(f"🌍 EN: {translation}")
        print(f"{'='*70}\n")
    
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
