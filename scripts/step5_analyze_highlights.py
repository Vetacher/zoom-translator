#!/usr/bin/env python3
"""
Этап 5: Анализ лучших моментов (только текст)
- GPT анализирует переводы
- Выделяет самые ценные моменты
- Создает список с таймкодами и описаниями
- БЕЗ нарезки видео
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Azure OpenAI config
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY')
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"


def analyze_highlights(client, segments):
    """Analyze content and identify best moments"""
    
    # Create content summary
    content_summary = []
    for seg in segments:
        content_summary.append({
            "id": seg['segment_id'],
            "time": seg['start_time'],
            "speaker": seg['speaker'],
            "russian": seg['original'][:300],
            "english": seg['translation'][:300]
        })
    
    # Sample if too long
    if len(content_summary) > 150:
        step = len(content_summary) // 150
        content_summary = content_summary[::step]
    
    content_json = json.dumps(content_summary, ensure_ascii=False, indent=2)
    
    prompt = f"""Analyze this business/tech presentation about product development, startups, vibe coding, and low-code/no-code tools.

TASK: Identify 6-10 BEST moments for a 2-3 minute highlight reel.

CRITERIA for valuable moments:
1. **Actionable advice** - practical tips viewers can immediately use
2. **Surprising insights** - counter-intuitive or eye-opening ideas  
3. **Strong hooks** - attention-grabbing statements that make people want to watch
4. **Key concepts** - important methodologies (SCAMPER, MicroSaaS, vibe coding, etc.)
5. **Real examples** - concrete case studies, numbers, success/failure stories
6. **Controversial takes** - opinions that challenge conventional wisdom

AVOID:
- Generic "hello/goodbye" statements
- Pure transitions without substance
- Overly technical jargon without explanation
- Filler words and rambling

CONTENT:
{content_json}

Return ONLY a JSON array:
[
  {{
    "segment_id": 123,
    "time_start": "00:12:34.000",
    "estimated_duration_seconds": 35,
    "title": "Short catchy title",
    "reason": "Why this moment is valuable",
    "hook_quote": "Exact quote that grabs attention (in English)",
    "key_points": ["point 1", "point 2"],
    "clip_description": "What happens in this moment",
    "engagement_score": 9
  }}
]

- Select 6-10 moments
- Total duration: 120-180 seconds
- engagement_score: 1-10 (how interesting/valuable)
- Order by importance (best first)

Return ONLY valid JSON."""

    try:
        print(f"  🤔 Analyzing content with GPT-4o...")
        
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert content analyst identifying the most valuable moments from educational presentations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=3000
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
        print(f"  ❌ Error: {e}")
        print(f"  Response: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        return None


def find_segment_by_id(segments, segment_id):
    """Find segment by ID"""
    for seg in segments:
        if seg['segment_id'] == segment_id:
            return seg
    return None


def analyze_content_highlights(translation_path: str, output_path: str):
    """Analyze content and create highlights report"""
    
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
    
    # Initialize OpenAI
    print(f"\n🔧 Initializing Azure OpenAI...")
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    # Analyze
    print(f"\n🎬 Analyzing content for best moments...")
    highlights = analyze_highlights(client, segments)
    
    if not highlights:
        print(f"❌ Failed to identify highlights")
        return False
    
    # Enrich with actual segment data
    enriched_highlights = []
    
    for highlight in highlights:
        segment_id = highlight['segment_id']
        segment = find_segment_by_id(segments, segment_id)
        
        if segment:
            # Calculate end time
            start_ms = segment['start_ms']
            duration_s = highlight.get('estimated_duration_seconds', 30)
            end_ms = start_ms + (duration_s * 1000)
            
            # Find natural end point (look ahead for pauses)
            for next_id in range(segment_id + 1, min(segment_id + 10, len(segments) + 1)):
                next_seg = find_segment_by_id(segments, next_id)
                if next_seg and next_seg['end_ms'] <= end_ms:
                    end_ms = next_seg['end_ms']
            
            enriched = {
                **highlight,
                "time_end": format_time_ms(end_ms),
                "actual_start_ms": start_ms,
                "actual_end_ms": end_ms,
                "actual_duration_seconds": (end_ms - start_ms) / 1000,
                "russian_text": segment['original'],
                "english_text": segment['translation'],
                "speaker": segment['speaker'],
                "gender": segment.get('gender', 'unknown')
            }
            
            enriched_highlights.append(enriched)
    
    # Save report
    report = {
        "video_file": str(translation_file).replace('_translated_fixed.json', '_english.mp4'),
        "total_highlights": len(enriched_highlights),
        "total_duration_seconds": sum(h['actual_duration_seconds'] for h in enriched_highlights),
        "highlights": enriched_highlights
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Display results
    print(f"\n✅ Analysis complete! Found {len(enriched_highlights)} highlight moments:\n")
    print("=" * 80)
    
    total_duration = 0
    
    for i, highlight in enumerate(enriched_highlights, 1):
        duration = highlight['actual_duration_seconds']
        total_duration += duration
        
        print(f"\n🎬 HIGHLIGHT #{i} - {highlight['title']}")
        print(f"   ⭐ Engagement Score: {highlight.get('engagement_score', 'N/A')}/10")
        print(f"   ⏱️  Time: {highlight['time_start']} → {highlight['time_end']} ({duration:.1f}s)")
        print(f"   🗣️  Speaker: {highlight['speaker']} ({highlight['gender']})")
        print(f"\n   📝 Why valuable:")
        print(f"      {highlight['reason']}")
        print(f"\n   🔥 Hook quote:")
        print(f"      \"{highlight['hook_quote']}\"")
        print(f"\n   💡 Key points:")
        for point in highlight.get('key_points', []):
            print(f"      • {point}")
        print(f"\n   🇷🇺 Russian: {highlight['russian_text'][:150]}...")
        print(f"   🇬🇧 English: {highlight['english_text'][:150]}...")
        print(f"\n   ✂️  FFmpeg command to extract:")
        print(f"      ffmpeg -i videos/original_english.mp4 -ss {highlight['time_start']} "
              f"-t {duration:.1f} -c copy videos/clip_{i:02d}.mp4")
        print("-" * 80)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total clips: {len(enriched_highlights)}")
    print(f"   Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    print(f"   Average engagement: {sum(h.get('engagement_score', 0) for h in enriched_highlights) / len(enriched_highlights):.1f}/10")
    print(f"\n💾 Detailed report saved to: {output_path}")
    
    # Create bash script for easy extraction
    script_path = output_path.replace('.json', '_extract.sh')
    with open(script_path, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Extract all highlight clips\n")
        f.write("mkdir -p videos/clips\n\n")
        
        for i, highlight in enumerate(enriched_highlights, 1):
            duration = highlight['actual_duration_seconds']
            f.write(f"# Clip {i}: {highlight['title']}\n")
            f.write(f"ffmpeg -i videos/original_english.mp4 -ss {highlight['time_start']} "
                   f"-t {duration:.1f} -c copy videos/clips/clip_{i:02d}.mp4\n\n")
        
        f.write("# Concatenate all clips\n")
        f.write("cat > /tmp/clips_list.txt << EOF\n")
        for i in range(1, len(enriched_highlights) + 1):
            f.write(f"file 'clips/clip_{i:02d}.mp4'\n")
        f.write("EOF\n\n")
        f.write("ffmpeg -f concat -safe 0 -i /tmp/clips_list.txt -c copy videos/original_english_highlights.mp4\n")
    
    print(f"📜 Extraction script saved to: {script_path}")
    print(f"\n   Run: bash {script_path}")
    
    return True


def format_time_ms(ms):
    """Format milliseconds to HH:MM:SS.mmm"""
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step5_analyze_highlights.py <translation_json>")
        print("Example: python step5_analyze_highlights.py videos/original_translated_fixed.json")
        sys.exit(1)
    
    translation_path = sys.argv[1]
    output_path = translation_path.replace('_translated_fixed.json', '_highlights.json')
    
    success = analyze_content_highlights(translation_path, output_path)
    sys.exit(0 if success else 1)
