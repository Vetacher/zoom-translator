#!/usr/bin/env python3
"""
Этап 1: Извлечение аудио из видео
"""

import subprocess
import sys
from pathlib import Path

def extract_audio(video_path: str, output_audio: str):
    """Извлекает аудио из видео используя ffmpeg"""
    
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"❌ Видео не найдено: {video_path}")
        return False
    
    print(f"📹 Видео: {video_file.name}")
    print(f"🎵 Извлекаем аудио...")
    
    # FFmpeg команда для извлечения аудио
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',  # Без видео
        '-acodec', 'pcm_s16le',  # WAV формат
        '-ar', '16000',  # 16kHz (оптимально для Speech-to-Text)
        '-ac', '1',  # Mono
        '-y',  # Перезаписать если существует
        output_audio
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        output_file = Path(output_audio)
        if output_file.exists():
            size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"✅ Аудио извлечено: {output_audio}")
            print(f"📊 Размер: {size_mb:.1f} MB")
            return True
        else:
            print(f"❌ Не удалось создать аудио файл")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка ffmpeg: {e.stderr}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step1_extract_audio.py <video_file>")
        print("Example: python step1_extract_audio.py videos/original.mp4")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_audio = video_path.replace('.mp4', '_audio.wav')
    
    success = extract_audio(video_path, output_audio)
    sys.exit(0 if success else 1)
