from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
import random

app = FastAPI()

clients = set()
clients_lock = asyncio.Lock()
broadcasting = False
broadcast_event = asyncio.Event()

@app.get("/start")
async def start_broadcast():
    global broadcasting
    broadcasting = True
    broadcast_event.set()
    return JSONResponse(content={"status": "started"})

@app.get("/stop")
async def stop_broadcast():
    global broadcasting
    broadcasting = False
    return JSONResponse(content={"status": "stopped"})

@app.get("/ping")
async def ping():
    return JSONResponse(content={"status": "ok"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async with clients_lock:
        clients.add(websocket)
    try:
        await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        async with clients_lock:
            clients.discard(websocket)

async def broadcast_numbers():
    while True:
        await broadcast_event.wait()
        if broadcasting:
            number = f"{random.randint(0, 9)}{random.randint(0, 9)}"
            message = {"number": number}
            async with clients_lock:
                disconnected = set()
                for client in clients:
                    try:
                        await client.send_json(message)
                    except:
                        disconnected.add(client)
                clients.difference_update(disconnected)
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_numbers())
