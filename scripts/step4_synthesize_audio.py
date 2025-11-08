#!/usr/bin/env python3
"""
Этап 4: Озвучка переводов с Azure TTS
- Синтезирует аудио для каждого сегмента
- Использует правильный голос по полу спикера
- Создает финальную аудиодорожку с таймингом
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
import time
import io

load_dotenv()

# Azure Speech Services
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION', 'westeurope')


class AzureTTSSynthesizer:
    """Synthesize speech using Azure TTS"""
    
    # Neural voices (best quality)
    VOICES = {
        "male": {
            "en-US": "en-US-GuyNeural",
            "ru-RU": "ru-RU-DmitryNeural"
        },
        "female": {
            "en-US": "en-US-JennyNeural",
            "ru-RU": "ru-RU-SvetlanaNeural"
        }
    }
    
    def __init__(self, speech_key: str, region: str, language: str = "en-US"):
        self.speech_key = speech_key
        self.region = region
        self.language = language
        
        # Configure Speech
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=region
        )
        
        # Use neural voices for best quality
        self.speech_config.speech_synthesis_voice_name = self.VOICES["female"][language]
    
    def synthesize(self, text: str, gender: str = "female", rate: str = "-10%") -> bytes:
        """Synthesize text to audio bytes with adjustable speed"""
        
        # Select voice based on gender
        voice_name = self.VOICES.get(gender, self.VOICES["female"])[self.language]
        
        # Create SSML for speed control
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
            <voice name="{voice_name}">
                <prosody rate="{rate}">
                    {text}
                </prosody>
            </voice>
        </speak>"""
        
        # Use synthesizer without audio output config to get raw data
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=None  # None = return audio data directly
        )
        
        try:
            result = synthesizer.speak_ssml_async(ssml).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # Get audio data
                audio_data = result.audio_data
                return audio_data
            else:
                print(f"  ❌ TTS error: {result.reason}")
                return None
                
        except Exception as e:
            print(f"  ❌ TTS exception: {e}")
            return None


def create_silence(duration_ms: int) -> AudioSegment:
    """Create silence audio segment"""
    return AudioSegment.silent(duration=duration_ms)


def synthesize_translation_audio(translation_path: str, output_audio: str):
    """Synthesize audio for all translations"""
    
    # Load translations
    translation_file = Path(translation_path)
    if not translation_file.exists():
        print(f"❌ Translation file not found: {translation_path}")
        return False
    
    print(f"📖 Loading translations: {translation_file.name}")
    
    with open(translation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get('segments', [])
    print(f"📊 Total segments: {len(segments)}")
    
    # Initialize TTS
    print(f"🔧 Initializing Azure TTS...")
    tts = AzureTTSSynthesizer(
        speech_key=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION,
        language="en-US"
    )
    
    # Create audio for each segment
    print(f"\n🎙️ Synthesizing audio with smart timing...")
    
    audio_segments = []
    current_position_ms = 0  # Where we are in the audio timeline
    accumulated_delay_ms = 0  # How much we're behind/ahead schedule
    
    for i, segment in enumerate(segments):
        seg_id = segment['segment_id']
        translation = segment['translation']
        gender = segment.get('gender', 'female')
        start_ms = segment.get('start_ms', 0)
        end_ms = segment.get('end_ms', 0)
        segment_duration = end_ms - start_ms
        
        # Skip filtered or error segments
        if translation.startswith('[FILTERED]') or translation.startswith('[Translation error'):
            print(f"  ⏭️ Skipping segment {seg_id} (filtered/error)")
            continue
        
        # Show progress
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Synthesizing segment {i+1}/{len(segments)}... (delay: {accumulated_delay_ms/1000:.1f}s)")
        
        # Calculate when this segment should ideally start
        ideal_start_ms = start_ms
        actual_start_ms = current_position_ms
        
        # If we're behind schedule (current position < ideal start)
        if actual_start_ms < ideal_start_ms:
            # Add silence to catch up
            silence_needed = ideal_start_ms - actual_start_ms
            silence = create_silence(int(silence_needed))
            audio_segments.append(silence)
            current_position_ms = ideal_start_ms
            accumulated_delay_ms = 0  # Reset delay
            
            if (i + 1) % 10 == 0 or i == 0:
                print(f"    + Added {silence_needed/1000:.1f}s silence to sync")
        
        # Synthesize audio
        audio_data = tts.synthesize(translation, gender)
        
        if audio_data:
            # Convert to AudioSegment (Azure returns WAV format)
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format="wav"
            )
            
            actual_duration = len(audio_segment)
            
            # Add this segment
            audio_segments.append(audio_segment)
            current_position_ms += actual_duration
            
            # Calculate delay: positive = we're running long, negative = we're running short
            accumulated_delay_ms = current_position_ms - end_ms
            
            # Log significant delays
            if abs(accumulated_delay_ms) > 2000 and (i + 1) % 10 == 0:
                if accumulated_delay_ms > 0:
                    print(f"    ⚠️ Running {accumulated_delay_ms/1000:.1f}s behind schedule")
                else:
                    print(f"    ✅ Running {-accumulated_delay_ms/1000:.1f}s ahead of schedule")
            
        else:
            print(f"  ⚠️ Failed to synthesize segment {seg_id}")
        
        # Rate limiting
        time.sleep(0.1)
    
    # Combine all audio segments
    print(f"\n🔗 Combining audio segments...")
    
    if not audio_segments:
        print(f"❌ No audio segments created!")
        return False
    
    final_audio = audio_segments[0]
    for segment in audio_segments[1:]:
        final_audio += segment
    
    # Export final audio
    print(f"💾 Exporting audio...")
    
    output_path = Path(output_audio)
    output_format = output_path.suffix[1:]  # Remove dot
    
    final_audio.export(
        output_audio,
        format=output_format,
        parameters=["-ar", "16000"]  # 16kHz sample rate
    )
    
    # Stats
    duration_seconds = len(final_audio) / 1000
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    
    print(f"\n✅ Audio synthesis completed!")
    print(f"📊 Total segments synthesized: {len(audio_segments)}")
    print(f"⏱️ Duration: {minutes}:{seconds:02d}")
    print(f"💾 Saved to: {output_audio}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step4_synthesize_audio.py <translation_json>")
        print("Example: python step4_synthesize_audio.py videos/original_translated_fixed.json")
        sys.exit(1)
    
    translation_path = sys.argv[1]
    output_audio = translation_path.replace('_translated_fixed.json', '_audio_en.wav')
    
    success = synthesize_translation_audio(translation_path, output_audio)
    sys.exit(0 if success else 1)
