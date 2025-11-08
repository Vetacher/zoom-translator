#!/usr/bin/env python3
import azure.cognitiveservices.speech as speechsdk
import assemblyai as aai
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
import subprocess
import os
from dotenv import load_dotenv
import time
import requests

load_dotenv()

print("=== Complete Translation Pipeline Comparison ===\n")

# Извлекаем аудио
video_file = '/tmp/test_webinar.mp4'
audio_file = '/tmp/test_audio.wav'

print("1. Extracting audio...")
subprocess.run([
    'ffmpeg', '-y', '-i', video_file,
    '-vn', '-acodec', 'pcm_s16le',
    '-ar', '16000', '-ac', '1',
    audio_file
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

duration_output = subprocess.check_output([
    'ffprobe', '-i', audio_file, '-show_entries', 
    'format=duration', '-v', 'quiet', '-of', 'csv=p=0'
]).decode().strip()

duration = float(duration_output)
print(f"   ✓ Audio extracted: {duration:.1f} seconds (~{duration/60:.1f} minutes)\n")

# Translator setup
translator_key = os.getenv('AZURE_TRANSLATOR_KEY')
translator_region = os.getenv('AZURE_TRANSLATOR_REGION')
translator_endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT')

translator = TextTranslationClient(
    endpoint=translator_endpoint,
    credential=AzureKeyCredential(translator_key),
    region=translator_region
)

# TTS setup
speech_key = os.getenv('AZURE_SPEECH_KEY')
speech_region = os.getenv('AZURE_SPEECH_REGION')

results = {}

print("="*70)
print("\n2. Azure Speech-to-Text + Azure TTS\n")

speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "ru-RU"
audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

azure_results = []

def recognized(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        azure_results.append(evt.result.text)
        print(".", end="", flush=True)

recognizer.recognized.connect(recognized)
recognizer.start_continuous_recognition()

time.sleep(int(duration) + 10)
recognizer.stop_continuous_recognition()

azure_transcript = " ".join(azure_results)
print(f"\n   Words recognized: {len(azure_transcript.split())}")
print(f"   EN: {azure_transcript[:150]}...")

if azure_transcript:
    result = translator.translate(
        body=[{"text": azure_transcript}],
        to_language=['en'],
        from_language='ru'
    )
    azure_translation = result[0].translations[0].text
    print(f"   RU: {azure_translation[:150]}...")
    
    # Azure TTS
    print("   Generating audio (Azure TTS)...")
    tts_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    tts_config.speech_synthesis_voice_name = "ru-RU-DmitryNeural"
    audio_output = speechsdk.audio.AudioOutputConfig(filename="/tmp/azure_tts_output.wav")
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config, audio_config=audio_output)
    
    # Берём первые 500 символов для теста
    synthesizer.speak_text_async(azure_translation[:500]).get()
    print("   ✓ Audio saved to /tmp/azure_tts_output.wav")
    
    results['azure'] = {
        'transcript': azure_transcript,
        'translation': azure_translation,
        'words': len(azure_transcript.split()),
        'audio_file': '/tmp/azure_tts_output.wav'
    }

print("\n" + "="*70)
print("\n3. AssemblyAI + Azure TTS\n")

aai.settings.api_key = os.getenv('ASSEMBLYAI_API_KEY')
transcriber = aai.Transcriber()

print("   Transcribing...")
transcript = transcriber.transcribe(audio_file)

if transcript.status == aai.TranscriptStatus.completed:
    assemblyai_transcript = transcript.text
    print(f"   Words recognized: {len(assemblyai_transcript.split())}")
    print(f"   EN: {assemblyai_transcript[:150]}...")
    
    result = translator.translate(
        body=[{"text": assemblyai_transcript}],
        to_language=['en'],
        from_language='ru'
    )
    assemblyai_translation = result[0].translations[0].text
    print(f"   RU: {assemblyai_translation[:150]}...")
    
    # Azure TTS
    print("   Generating audio (Azure TTS)...")
    audio_output = speechsdk.audio.AudioOutputConfig(filename="/tmp/assemblyai_tts_output.wav")
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config, audio_config=audio_output)
    synthesizer.speak_text_async(assemblyai_translation[:500]).get()
    print("   ✓ Audio saved to /tmp/assemblyai_tts_output.wav")
    
    results['assemblyai'] = {
        'transcript': assemblyai_transcript,
        'translation': assemblyai_translation,
        'words': len(assemblyai_transcript.split()),
        'audio_file': '/tmp/assemblyai_tts_output.wav'
    }
else:
    print(f"   ✗ Error: {transcript.error}")

print("\n" + "="*70)
print("\n=== COMPARISON SUMMARY ===\n")

for service, data in results.items():
    print(f"{service.upper()}:")
    print(f"  Words: {data['words']}")
    print(f"  EN Sample: {data['transcript'][:100]}...")
    print(f"  RU Sample: {data['translation'][:100]}...")
    print(f"  Audio: {data['audio_file']}\n")

print("\nFull results saved to /tmp/")
for service, data in results.items():
    with open(f'/tmp/{service}_result.txt', 'w') as f:
        f.write(f"ENGLISH TRANSCRIPT:\n{data['transcript']}\n\n")
        f.write(f"RUSSIAN TRANSLATION:\n{data['translation']}\n")

print("\n✓ Download audio samples to compare TTS quality:")
print("  scp lisa@172.205.192.158:/tmp/azure_tts_output.wav ~/Downloads/")
print("  scp lisa@172.205.192.158:/tmp/assemblyai_tts_output.wav ~/Downloads/")
