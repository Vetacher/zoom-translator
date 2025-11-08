#!/usr/bin/env python3
"""
Этап 5: Извлечение лучших моментов для превью
- GPT анализирует весь контент
- Выбирает самые ценные/интересные моменты
- Создает клипы по 20-40 секунд
- Общая длительность 2-3 минуты
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI
import subprocess

load_dotenv()

# Azure OpenAI config
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY')
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"


def analyze_content_for_highlights(client, segments):
    """Use GPT to identify the most valuable moments"""
    
    # Create summary of all segments
    content_summary = []
    for seg in segments:
        content_summary.append({
            "id": seg['segment_id'],
            "time": seg['start_time'],
            "speaker": seg['speaker'],
            "text": seg['translation'][:200]  # Limit length
        })
    
    # Sample segments if too many (to fit in context)
    if len(content_summary) > 100:
        # Take every Nth segment to get ~100 samples
        step = len(content_summary) // 100
        content_summary = content_summary[::step]
    
    content_json = json.dumps(content_summary, ensure_ascii=False, indent=2)
    
    prompt = f"""You are analyzing a business/tech presentation about product development, startups, vibe coding, and low-code/no-code tools.

TASK: Identify the 5-8 MOST VALUABLE moments for a 2-3 minute highlight reel.

CRITERIA for valuable moments:
1. **Actionable advice** - practical tips viewers can use
2. **Surprising insights** - counter-intuitive or eye-opening ideas
3. **Strong hooks** - attention-grabbing statements
4. **Key concepts** - important methodologies (SCAMPER, MicroSaaS, etc.)
5. **Real examples** - concrete case studies or numbers

AVOID:
- Generic statements
- Filler content
- Introductions/transitions
- Overly technical details without context

PRESENTATION CONTENT:
{content_json}

Return ONLY a JSON array of the best moments:
[
  {{
    "segment_id": 123,
    "time": "00:12:34.000",
    "reason": "Explains SCAMPER methodology with concrete example",
    "hook": "Brief quote or key phrase",
    "duration_estimate": 30
  }},
  ...
]

Select 5-8 moments that together tell a compelling story. Total duration should be 2-3 minutes (120-180 seconds).
Return ONLY valid JSON, no explanations."""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert video editor identifying the most valuable moments from educational content."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        highlights = json.loads(response_text)
        return highlights
        
    except Exception as e:
        print(f"❌ Error analyzing content: {e}")
        return None


def find_segment_by_id(segments, segment_id):
    """Find segment by ID"""
    for seg in segments:
        if seg['segment_id'] == segment_id:
            return seg
    return None


def format_timestamp_for_ffmpeg(ms):
    """Convert milliseconds to HH:MM:SS.mmm format for ffmpeg"""
    seconds = ms / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def extract_video_clip(input_video, start_ms, end_ms, output_file):
    """Extract video clip using ffmpeg"""
    
    start_time = format_timestamp_for_ffmpeg(start_ms)
    duration_ms = end_ms - start_ms
    duration = duration_ms / 1000
    
    cmd = [
        'ffmpeg',
        '-i', input_video,
        '-ss', start_time,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-y',
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ FFmpeg error: {e.stderr.decode()}")
        return False


def concatenate_clips(clip_files, output_file):
    """Concatenate multiple video clips"""
    
    # Create file list for ffmpeg
    list_file = '/tmp/ffmpeg_concat_list.txt'
    with open(list_file, 'w') as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")
    
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        '-y',
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Concatenation error: {e.stderr.decode()}")
        return False


def create_highlights_video(translation_path: str, video_path: str, output_path: str):
    """Create highlights video"""
    
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
    
    # Check video file
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"❌ Video file not found: {video_path}")
        return False
    
    # Initialize OpenAI client
    print(f"🔧 Initializing Azure OpenAI client...")
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    # Analyze content for highlights
    print(f"\n🎬 Analyzing content for best moments...")
    highlights = analyze_content_for_highlights(client, segments)
    
    if not highlights:
        print(f"❌ Failed to identify highlights")
        return False
    
    print(f"\n✅ Found {len(highlights)} highlight moments:")
    for i, highlight in enumerate(highlights, 1):
        print(f"\n  {i}. [{highlight['time']}] ({highlight.get('duration_estimate', 30)}s)")
        print(f"     Reason: {highlight['reason']}")
        print(f"     Hook: {highlight.get('hook', 'N/A')}")
    
    # Extract clips
    print(f"\n✂️ Extracting video clips...")
    
    clip_files = []
    clips_dir = Path(video_path).parent / 'clips'
    clips_dir.mkdir(exist_ok=True)
    
    for i, highlight in enumerate(highlights, 1):
        segment_id = highlight['segment_id']
        segment = find_segment_by_id(segments, segment_id)
        
        if not segment:
            print(f"  ⚠️ Segment {segment_id} not found, skipping")
            continue
        
        # Get timing
        start_ms = segment['start_ms']
        
        # Estimate end time (add duration or use next segment)
        duration_estimate = highlight.get('duration_estimate', 30) * 1000  # Convert to ms
        end_ms = start_ms + duration_estimate
        
        # Find actual end (look for natural pause)
        for j in range(segment_id, min(segment_id + 5, len(segments))):
            next_seg = find_segment_by_id(segments, j + 1)
            if next_seg:
                potential_end = next_seg['end_ms']
                if potential_end - start_ms <= duration_estimate * 1.2:  # Within 120% of estimate
                    end_ms = potential_end
        
        # Extract clip
        clip_file = clips_dir / f"clip_{i:02d}.mp4"
        print(f"  Extracting clip {i}/{len(highlights)}: {clip_file.name}")
        
        if extract_video_clip(str(video_file), start_ms, end_ms, str(clip_file)):
            clip_files.append(str(clip_file))
            actual_duration = (end_ms - start_ms) / 1000
            print(f"    ✅ Duration: {actual_duration:.1f}s")
        else:
            print(f"    ❌ Failed to extract clip {i}")
    
    if not clip_files:
        print(f"\n❌ No clips extracted!")
        return False
    
    # Concatenate clips
    print(f"\n🔗 Combining {len(clip_files)} clips...")
    
    if concatenate_clips(clip_files, output_path):
        print(f"\n✅ Highlights video created!")
        
        # Calculate total duration
        total_duration = 0
        for highlight in highlights:
            total_duration += highlight.get('duration_estimate', 30)
        
        print(f"📊 Total clips: {len(clip_files)}")
        print(f"⏱️ Estimated duration: ~{total_duration}s ({total_duration/60:.1f} minutes)")
        print(f"💾 Saved to: {output_path}")
        
        return True
    else:
        print(f"\n❌ Failed to combine clips")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python step5_extract_highlights.py <translation_json> <video_file>")
        print("Example: python step5_extract_highlights.py videos/original_translated_fixed.json videos/original_english.mp4")
        sys.exit(1)
    
    translation_path = sys.argv[1]
    video_path = sys.argv[2]
    output_path = video_path.replace('.mp4', '_highlights.mp4')
    
    success = create_highlights_video(translation_path, video_path, output_path)
    sys.exit(0 if success else 1)
