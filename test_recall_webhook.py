from fastapi import FastAPI, Request
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/webhook/transcript")
async def receive_transcript(request: Request):
    data = await request.json()
    event = data.get('event')
    
    if event == 'transcript.data':
        transcript_data = data.get('data', {}).get('data', {})
        words = transcript_data.get('words', [])
        text = ' '.join([w['text'] for w in words])
        speaker = transcript_data.get('participant', {}).get('name', 'Unknown')
        
        print(f"\n{'='*60}")
        print(f"🎤 {speaker}: {text}")
        print(f"{'='*60}\n")
    
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
