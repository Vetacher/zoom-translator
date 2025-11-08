import os
import time
import requests
import ffmpeg
from dotenv import load_dotenv

# === Загружаем .env ===
load_dotenv()

VIDEO_FILE = "video.mp4"
OUTPUT_FILE = "video_trimmed.mp4"
MAX_SILENCE = 2.0  # секунды

# === Конфиг Azure Video Indexer ===
ACCOUNT_ID = os.getenv("AZURE_VIDEO_INDEXER_ACCOUNT_ID")
API_KEY = os.getenv("AZURE_VIDEO_INDEXER_KEY")
LOCATION = os.getenv("AZURE_VIDEO_INDEXER_LOCATION", "trial")

# === 1. Получаем access token ===
def get_access_token():
    url = f"https://api.videoindexer.ai/Auth/{LOCATION}/Accounts/{ACCOUNT_ID}/AccessToken"
    params = {"allowEdit": "true"}
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.text.strip('"')

# === 2. Загружаем видео ===
def upload_video(access_token):
    url = f"https://api.videoindexer.ai/{LOCATION}/Accounts/{ACCOUNT_ID}/Videos"
    params = {"accessToken": access_token, "name": "temp_video"}
    with open(VIDEO_FILE, "rb") as f:
        files = {"file": f}
        response = requests.post(url, params=params, files=files)
    response.raise_for_status()
    video_id = response.json()['id']
    print("Video uploaded, id:", video_id)
    return video_id

# === 3. Получаем транскрипт и таймкоды ===
def get_insights(access_token, video_id):
    url = f"https://api.videoindexer.ai/{LOCATION}/Accounts/{ACCOUNT_ID}/Videos/{video_id}/Index"
    params = {"accessToken": access_token}
    while True:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('state') == 'Processed':
            break
        print("Processing...", data.get('state'))
        time.sleep(5)
    return data

# === 4. Объединяем сегменты с короткими паузами ===
def merge_segments(insights, max_silence=2.0):
    segments = []
    speech_segments = insights['videos'][0]['insights']['speechSegments']
    for s in speech_segments:
        start = float(s['instances'][0]['start'])
        end = float(s['instances'][0]['end'])
        segments.append((start, end))
    
    merged = []
    if not segments:
        return merged
    
    cur_start, cur_end = segments[0]
    for start, end in segments[1:]:
        if start - cur_end <= max_silence:
            cur_end = end
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged

# === 5. Нарезка видео с помощью ffmpeg ===
def trim_video(segments):
    input_video = ffmpeg.input(VIDEO_FILE)
    clips = []
    for start, end in segments:
        clips.append(input_video.trim(start=start, end=end).setpts('PTS-STARTPTS'))
    joined = ffmpeg.concat(*clips, v=1, a=1)
    joined.output(OUTPUT_FILE).run()
    print("Trimmed video saved as", OUTPUT_FILE)

# === Main ===
def main():
    token = get_access_token()
    video_id = upload_video(token)
    insights = get_insights(token, video_id)
    segments = merge_segments(insights, max_silence=MAX_SILENCE)
    trim_video(segments)

if __name__ == "__main__":
    main()
