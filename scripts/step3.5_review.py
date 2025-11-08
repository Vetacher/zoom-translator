#!/usr/bin/env python3
"""
Этап 3.5: Проверка консистентности и исправление странностей в переводе
- GPT-4o анализирует весь контекст
- Исправляет очевидные ошибки транскрипции
- Улучшает переводы учитывая контекст
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


def analyze_and_fix_translations(client, segments_batch, batch_num):
    """Analyze batch of segments for consistency and fix issues"""
    
    # Prepare context for GPT
    context = []
    for seg in segments_batch:
        context.append({
            "id": seg['segment_id'],
            "speaker": seg['speaker'],
            "original": seg['original'],
            "translation": seg['translation'],
            "time": seg['start_time']
        })
    
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    
    prompt = f"""You are reviewing Russian-to-English translations for consistency and accuracy.

TASK:
1. Review these translation segments
2. Look for obvious transcription errors in Russian (e.g., "Папа" when context suggests "Дам/Даю")
3. Check if translations are consistent with context
4. Fix any strange or incorrect translations
5. Ensure technical terms are translated correctly

CONTEXT: This is a business/tech presentation about product development, startups, vibe coding, low-code/no-code tools.

SEGMENTS TO REVIEW:
{context_json}

INSTRUCTIONS:
- Return ONLY a JSON array with fixed segments
- Keep the same structure: [{{"id": 1, "original_fixed": "...", "translation_fixed": "..."}}, ...]
- If segment is OK, return original/translation as-is
- Fix obvious transcription errors (like "Папа" → "Дам")
- Improve translations based on context
- Keep it concise and professional

Return only valid JSON, no explanations."""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert translator and editor reviewing Russian-to-English translations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        fixes = json.loads(response_text)
        return fixes
        
    except Exception as e:
        print(f"  ⚠️ Error analyzing batch {batch_num}: {e}")
        return None


def review_and_fix_translations(input_path: str, output_path: str):
    """Review and fix translation file"""
    
    # Load translations
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ Translation file not found: {input_path}")
        return False
    
    print(f"📖 Loading translations: {input_file.name}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get('segments', [])
    print(f"📊 Total segments: {len(segments)}")
    
    # Initialize OpenAI client
    print(f"🔧 Initializing Azure OpenAI client...")
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    # Process in batches (10 segments at a time for better context)
    print(f"\n🔍 Analyzing translations for consistency...")
    batch_size = 10
    fixed_segments = []
    
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(segments) + batch_size - 1) // batch_size
        
        print(f"  Processing batch {batch_num}/{total_batches} (segments {i+1}-{min(i+batch_size, len(segments))})...")
        
        # Get fixes from GPT
        fixes = analyze_and_fix_translations(client, batch, batch_num)
        
        if fixes:
            # Apply fixes
            fixes_dict = {fix['id']: fix for fix in fixes}
            
            for seg in batch:
                seg_id = seg['segment_id']
                if seg_id in fixes_dict:
                    fix = fixes_dict[seg_id]
                    
                    # Check if anything changed
                    original_changed = 'original_fixed' in fix and fix['original_fixed'] != seg['original']
                    translation_changed = 'translation_fixed' in fix and fix['translation_fixed'] != seg['translation']
                    
                    if original_changed or translation_changed:
                        print(f"    ✏️ Fixed segment {seg_id}:")
                        
                        if original_changed:
                            print(f"       Original: {seg['original'][:60]}...")
                            print(f"       Fixed:    {fix['original_fixed'][:60]}...")
                        
                        if translation_changed:
                            print(f"       Translation: {seg['translation'][:60]}...")
                            print(f"       Fixed:       {fix['translation_fixed'][:60]}...")
                    
                    # Update segment
                    seg['original'] = fix.get('original_fixed', seg['original'])
                    seg['translation'] = fix.get('translation_fixed', seg['translation'])
                
                fixed_segments.append(seg)
        else:
            # If batch failed, keep originals
            fixed_segments.extend(batch)
        
        # Rate limiting
        time.sleep(1)
    
    # Update data
    data['segments'] = fixed_segments
    data['reviewed'] = True
    data['review_notes'] = 'Reviewed and fixed by GPT-4o for consistency'
    
    # Save fixed translations
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Review completed!")
    print(f"💾 Saved to: {output_path}")
    
    # Show some examples of fixes
    print(f"\n📝 Summary of fixes:")
    changes_count = sum(1 for seg in fixed_segments if seg.get('_fixed', False))
    print(f"  Changed segments: {changes_count}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step3.5_review.py <translated_json>")
        print("Example: python step3.5_review.py videos/original_translated.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = input_path.replace('_translated.json', '_translated_fixed.json')
    
    success = review_and_fix_translations(input_path, output_path)
    sys.exit(0 if success else 1)
