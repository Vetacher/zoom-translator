from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()

@app.websocket("/ws/audio")
async def ws(websocket: WebSocket):
    await websocket.accept()
    print("✅ Connected!")
    
    count = 0
    while True:
        data = await websocket.receive_json()
        count += 1
        print(f"📨 Message #{count}: event={data.get('event')}")
        
        # Покажем структуру первого сообщения
        if count == 1:
            print(f"Full data keys: {data.keys()}")

uvicorn.run(app, host="0.0.0.0", port=8001)
