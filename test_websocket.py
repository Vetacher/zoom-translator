from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()

@app.websocket("/ws/audio")
async def ws(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connected!")
    
    while True:
        data = await websocket.receive_json()
        print(f"📨 Received: {data.get('event')}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
