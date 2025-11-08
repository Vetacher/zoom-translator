#!/usr/bin/env python3
"""
Этап 3: Перевод транскрипции с GPT-4o
- Использование glossary для точных терминов
- Фильтрация мусорных слов (filler words)
- Сохранение оригинала и перевода
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI
import time

load_dotenv()

# Azure OpenAI config
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY')
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

# Load glossary
GLOSSARY_PATH = Path(__file__).parent / 'config' / 'translation_glossary.json'


def load_glossary():
    """Load glossary from JSON"""
    try:
        if GLOSSARY_PATH.exists():
            with open(GLOSSARY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Не удалось загрузить glossary: {e}")
    return {}


def build_glossary_context(glossary):
    """Build glossary context for GPT prompt"""
    glossary_terms = []
    
    for ru_term, data in glossary.items():
        # Skip comment entries
        if ru_term.startswith('_comment'):
            continue
            
        en_term = data.get('en', '')
        alternatives = data.get('alternatives', [])
        description = data.get('description', '')
        
        if en_term:
            # Format: Russian variants → English
            all_variants = [ru_term] + alternatives
            variants_str = " / ".join(all_variants[:5])  # Limit to 5 variants
            glossary_terms.append(f"  • {variants_str} → {en_term}")
    
    if glossary_terms:
        context = "\n\nIMPORTANT TERMINOLOGY (use these exact translations):\n"
        context += "\n".join(glossary_terms[:50])  # Limit to 50 terms to fit in context
        return context
    
    return ""


def translate_text(client, text: str, glossary_context: str) -> str:
    """Translate text using Azure OpenAI with glossary"""
    
    system_prompt = f"""You are a professional Russian to English translator.

RULES:
1. Translate Russian to English accurately
2. Remove filler words: "ну", "вот", "так", "значит", "то есть", "как бы", "в общем", "короче", etc.
3. Make the text clean and professional
4. Preserve the meaning and tone
5. Use terminology from the glossary below
6. If you hear something that sounds like an English term (e.g., "вайт кодин" = "vibe coding"), use the correct English spelling
7. DO NOT translate names of people, companies, or products unless specified in glossary
8. Return ONLY the translation, no explanations
{glossary_context}
"""
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        error_str = str(e)
        
        # Check if content filter error
        if "content_filter" in error_str or "ResponsibleAIPolicyViolation" in error_str:
            return "[CONTENT_FILTERED]"
        
        print(f"❌ Translation error: {e}")
        return f"[Translation error]"


def translate_transcription(transcription_path: str, output_path: str):
    """Translate transcription JSON"""
    
    # Load transcription
    transcription_file = Path(transcription_path)
    if not transcription_file.exists():
        print(f"❌ Transcription file not found: {transcription_path}")
        return False
    
    print(f"📖 Loading transcription: {transcription_file.name}")
    
    with open(transcription_file, 'r', encoding='utf-8') as f:
        transcription_data = json.load(f)
    
    segments = transcription_data.get('segments', [])
    print(f"📊 Total segments: {len(segments)}")
    
    # Load glossary
    print(f"📚 Loading glossary...")
    glossary = load_glossary()
    glossary_context = build_glossary_context(glossary)
    
    if glossary:
        print(f"✅ Glossary loaded: {len(glossary)} terms")
        print(f"📝 Glossary context size: {len(glossary_context)} characters")
    else:
        print(f"⚠️ No glossary found, translating without it")
    
    # Initialize OpenAI client
    print(f"🔧 Initializing Azure OpenAI client...")
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    # Translate segments
    print(f"\n🌍 Starting translation...")
    translated_segments = []
    
    for i, segment in enumerate(segments):
        speaker = segment.get('speaker', 'Unknown')
        original_text = segment.get('text', '')
        start_time = segment.get('start_time', '')
        
        if not original_text:
            continue
        
        # Show progress
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Translating segment {i+1}/{len(segments)}...")
        
        # Translate
        translation = translate_text(client, original_text, glossary_context)
        
        # Check if content filter blocked
        if translation == "[CONTENT_FILTERED]":
            print(f"  ⚠️ Segment {i+1} blocked by content filter")
            # Keep original for manual review
            translation = f"[FILTERED] {original_text}"
        
        # Add to results
        translated_segment = {
            "segment_id": i + 1,
            "speaker": speaker,
            "gender": segment.get('gender', 'unknown'),
            "start_time": start_time,
            "end_time": segment.get('end_time', ''),
            "start_ms": segment.get('start_ms', 0),
            "end_ms": segment.get('end_ms', 0),
            "duration_ms": segment.get('duration_ms', 0),
            "original": original_text,
            "translation": translation,
            "confidence": segment.get('confidence', 0.0)
        }
        
        translated_segments.append(translated_segment)
        
        # Rate limiting (to avoid API throttling)
        time.sleep(0.1)
    
    # Save translated data
    output_data = {
        "audio_file": transcription_data.get('audio_file', ''),
        "source_language": "ru-RU",
        "target_language": "en-US",
        "total_segments": len(translated_segments),
        "speakers": transcription_data.get('speakers', {}),
        "glossary_used": bool(glossary),
        "glossary_terms_count": len(glossary) if glossary else 0,
        "translation_service": "Azure OpenAI GPT-4o",
        "segments": translated_segments
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Translation completed!")
    print(f"📊 Translated segments: {len(translated_segments)}")
    print(f"👥 Speakers: {len(transcription_data.get('speakers', {}))}")
    if glossary:
        print(f"📚 Glossary terms used: {len(glossary)}")
    print(f"💾 Saved to: {output_path}")
    
    # Show sample translations
    print(f"\n📝 Sample translations:")
    for segment in translated_segments[:3]:
        print(f"\n  [{segment['start_time']}] {segment['speaker']}:")
        print(f"  🇷🇺 {segment['original'][:100]}...")
        print(f"  🇬🇧 {segment['translation'][:100]}...")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step3_translate.py <transcription_json>")
        print("Example: python step3_translate.py videos/original_transcription.json")
        sys.exit(1)
    
    transcription_path = sys.argv[1]
    output_path = transcription_path.replace('_transcription.json', '_translated.json')
    
    success = translate_transcription(transcription_path, output_path)
    sys.exit(0 if success else 1)
