#!/usr/bin/env python3
"""
Этап 2: Транскрипция с Azure Speech Services
- Определение спикеров (diarization)
- Временные метки
- Использование glossary для phrase hints
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from datetime import timedelta

load_dotenv()

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


def build_phrase_list(glossary):
    """Build phrase list from glossary for Azure Speech recognition"""
    phrases = []
    
    for term, data in glossary.items():
        # Skip comment entries
        if term.startswith('_comment'):
            continue
            
        # Add main term
        if term and not term.startswith('_'):
            phrases.append(term)
        
        # Add English translation
        en_term = data.get('en', '')
        if en_term and en_term not in phrases:
            phrases.append(en_term)
        
        # Add alternatives (limit to avoid too many phrases)
        alternatives = data.get('alternatives', [])
        for alt in alternatives[:3]:  # Limit to 3 alternatives per term
            if alt and alt not in phrases:
                phrases.append(alt)
    
    return phrases


def format_time(milliseconds):
    """Format milliseconds to HH:MM:SS.mmm"""
    td = timedelta(milliseconds=milliseconds / 10000)  # Azure uses 100ns ticks
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    ms = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def transcribe_audio(audio_path: str, output_json: str):
    """Транскрибирует аудио с определением спикеров"""
    
    audio_file = Path(audio_path)
    if not audio_file.exists():
        print(f"❌ Аудио не найдено: {audio_path}")
        return False
    
    print(f"🎵 Аудио: {audio_file.name}")
    print(f"📝 Начинаем транскрипцию с определением спикеров...")
    
    # Load glossary
    print(f"📚 Загружаем glossary...")
    glossary = load_glossary()
    if glossary:
        print(f"✅ Glossary загружен: {len(glossary)} терминов")
    else:
        print(f"⚠️ Glossary не загружен, продолжаем без него")
    
    print(f"⏳ Это может занять несколько минут...")
    
    # Configure Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=os.getenv('AZURE_SPEECH_KEY'),
        region=os.getenv('AZURE_SPEECH_REGION', 'westeurope')
    )
    speech_config.speech_recognition_language = "ru-RU"
    speech_config.output_format = speechsdk.OutputFormat.Detailed
    
    # Enable speaker diarization
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
        "Continuous"
    )
    
    # Audio config
    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_file))
    
    # Create conversation transcriber for speaker diarization
    conversation_transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config,
        audio_config=audio_config
    )
    
    # Add phrase hints from glossary
    if glossary:
        try:
            phrases = build_phrase_list(glossary)
            if phrases:
                # Azure Speech supports phrase list for better recognition
                phrase_list_grammar = speechsdk.PhraseListGrammar.from_recognizer(conversation_transcriber)
                
                # Add phrases in batches (Azure has limits on phrase list size)
                added_count = 0
                for phrase in phrases[:1000]:  # Limit to 1000 phrases
                    try:
                        phrase_list_grammar.addPhrase(phrase)
                        added_count += 1
                    except Exception as e:
                        # Some phrases might fail, continue with others
                        pass
                
                print(f"✅ Добавлено {added_count} phrase hints из glossary")
        except Exception as e:
            print(f"⚠️ Не удалось добавить phrase hints: {e}")
            print(f"   Продолжаем транскрипцию без phrase hints")
    
    # Storage for results
    transcription_results = []
    all_done = False
    
    def transcribed_handler(evt):
        """Handle transcribed segments"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Get speaker ID
            speaker_id = evt.result.speaker_id if hasattr(evt.result, 'speaker_id') else "Unknown"
            
            # Get timing
            offset_ms = evt.result.offset / 10000  # Convert from 100ns ticks to ms
            duration_ms = evt.result.duration / 10000
            
            # Get text
            text = evt.result.text
            
            # Try to get detailed results with confidence
            try:
                import json
                detailed = json.loads(evt.result.json)
                best = detailed.get('NBest', [{}])[0]
                confidence = best.get('Confidence', 0.0)
                words = best.get('Words', [])
            except:
                confidence = 0.0
                words = []
            
            result = {
                "speaker": speaker_id,
                "text": text,
                "start_time": format_time(evt.result.offset),
                "end_time": format_time(evt.result.offset + evt.result.duration),
                "start_ms": offset_ms,
                "end_ms": offset_ms + duration_ms,
                "duration_ms": duration_ms,
                "confidence": confidence,
                "words": words
            }
            
            transcription_results.append(result)
            
            # Progress indicator
            print(f"  [{result['start_time']}] {speaker_id}: {text[:80]}...")
    
    def session_stopped_handler(evt):
        """Handle session stopped"""
        nonlocal all_done
        all_done = True
    
    def canceled_handler(evt):
        """Handle cancellation"""
        print(f"❌ Транскрипция отменена: {evt.reason}")
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f"❌ Ошибка: {evt.error_details}")
        nonlocal all_done
        all_done = True
    
    # Connect callbacks
    conversation_transcriber.transcribed.connect(transcribed_handler)
    conversation_transcriber.session_stopped.connect(session_stopped_handler)
    conversation_transcriber.canceled.connect(canceled_handler)
    
    # Start transcription
    conversation_transcriber.start_transcribing_async()
    
    # Wait for completion
    import time
    while not all_done:
        time.sleep(0.5)
    
    conversation_transcriber.stop_transcribing_async()
    
    # Infer gender for each speaker
    speakers = {}
    for result in transcription_results:
        speaker = result['speaker']
        if speaker not in speakers:
            # Alternate gender assignment (simple heuristic)
            gender = "female" if len(speakers) % 2 == 0 else "male"
            speakers[speaker] = gender
            result['gender'] = gender
        else:
            result['gender'] = speakers[speaker]
    
    # Save results
    output_data = {
        "audio_file": str(audio_file),
        "language": "ru-RU",
        "total_segments": len(transcription_results),
        "speakers": speakers,
        "glossary_used": bool(glossary),
        "glossary_terms_count": len(glossary) if glossary else 0,
        "segments": transcription_results
    }
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Транскрипция завершена!")
    print(f"📊 Сегментов: {len(transcription_results)}")
    print(f"👥 Спикеров: {len(speakers)}")
    for speaker, gender in speakers.items():
        print(f"   {speaker}: {gender}")
    if glossary:
        print(f"📚 Использован glossary: {len(glossary)} терминов")
    print(f"💾 Сохранено: {output_json}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step2_transcribe.py <audio_file>")
        print("Example: python step2_transcribe.py videos/original_audio.wav")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_json = audio_path.replace('_audio.wav', '_transcription.json')
    
    success = transcribe_audio(audio_path, output_json)
    sys.exit(0 if success else 1)
