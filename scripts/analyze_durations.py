#!/usr/bin/env python3
"""
Анализ длительности сегментов: сравнение оригинала и TTS
"""

import json
import sys

def analyze_segment_durations(json_path):
    """Analyze which segments are longer/shorter"""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get('segments', [])
    
    print(f"📊 Analyzing {len(segments)} segments...\n")
    
    total_original_ms = 0
    total_expected_ms = 0
    
    longer_segments = []
    shorter_segments = []
    
    for seg in segments:
        original_duration = seg['duration_ms']
        
        # Estimate TTS duration based on word count
        text = seg['translation']
        words = len(text.split())
        
        # Average speaking rate: ~150 words per minute = 2.5 words/sec = 400ms/word
        estimated_tts_duration = words * 400
        
        total_original_ms += original_duration
        total_expected_ms += estimated_tts_duration
        
        diff = estimated_tts_duration - original_duration
        diff_percent = (diff / original_duration * 100) if original_duration > 0 else 0
        
        if diff > 1000:  # More than 1 second longer
            longer_segments.append({
                'id': seg['segment_id'],
                'time': seg['start_time'],
                'original_ms': original_duration,
                'estimated_tts_ms': estimated_tts_duration,
                'diff_ms': diff,
                'diff_percent': diff_percent,
                'text': text[:100]
            })
        elif diff < -1000:  # More than 1 second shorter
            shorter_segments.append({
                'id': seg['segment_id'],
                'time': seg['start_time'],
                'original_ms': original_duration,
                'estimated_tts_ms': estimated_tts_duration,
                'diff_ms': diff,
                'diff_percent': diff_percent,
                'text': text[:100]
            })
    
    # Results
    print(f"⏱️  TOTAL DURATION COMPARISON:")
    print(f"   Original (Russian): {total_original_ms/1000:.1f}s ({total_original_ms/60000:.1f} min)")
    print(f"   Estimated TTS (English): {total_expected_ms/1000:.1f}s ({total_expected_ms/60000:.1f} min)")
    print(f"   Difference: {(total_expected_ms - total_original_ms)/1000:.1f}s ({(total_expected_ms - total_original_ms)/60000:.1f} min)")
    
    print(f"\n📈 LONGER SEGMENTS (TTS > Original by >1s): {len(longer_segments)}")
    for seg in longer_segments[:10]:
        print(f"\n   Segment #{seg['id']} [{seg['time']}]")
        print(f"   Original: {seg['original_ms']/1000:.1f}s | TTS: {seg['estimated_tts_ms']/1000:.1f}s")
        print(f"   Diff: +{seg['diff_ms']/1000:.1f}s (+{seg['diff_percent']:.0f}%)")
        print(f"   Text: {seg['text']}...")
    
    print(f"\n📉 SHORTER SEGMENTS (TTS < Original by >1s): {len(shorter_segments)}")
    for seg in shorter_segments[:10]:
        print(f"\n   Segment #{seg['id']} [{seg['time']}]")
        print(f"   Original: {seg['original_ms']/1000:.1f}s | TTS: {seg['estimated_tts_ms']/1000:.1f}s")
        print(f"   Diff: {seg['diff_ms']/1000:.1f}s ({seg['diff_percent']:.0f}%)")
        print(f"   Text: {seg['text']}...")
    
    # Check last segment
    last_seg = segments[-1]
    print(f"\n🏁 LAST SEGMENT:")
    print(f"   Segment #{last_seg['segment_id']}")
    print(f"   End time: {last_seg['end_time']}")
    print(f"   End ms: {last_seg['end_ms']/1000:.1f}s ({last_seg['end_ms']/60000:.1f} min)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_durations.py <translation_json>")
        sys.exit(1)
    
    analyze_segment_durations(sys.argv[1])
