from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import requests
import asyncio
from bs4 import BeautifulSoup
from typing import Set

app = FastAPI()
connected_clients: Set[WebSocket] = set()
is_running: bool = False

@app.get("/start")
async def start_stream():
    global is_running
    is_running = True
    return {"status": "started"}

@app.get("/stop")
async def stop_stream():
    global is_running
    is_running = False
    return {"status": "stopped"}

@app.get("/get")
async def get_current_data():
    return await fetch_set_data()

@app.post("/send")
async def broadcast_data(data: dict):
    global is_running
    is_running = False
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_json(data)
        except Exception:
            disconnected.add(client)
    connected_clients.difference_update(disconnected)
    # return {"status": "sent", "disconnected_clients": len(disconnected)}
    return await fetch_set_data()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        connected_clients.remove(websocket)

@app.on_event("startup")
async def start_background_task():
    async def stream_task():
        while True:
            if is_running:
                data = await fetch_set_data()
                disconnected = set()
                for client in connected_clients:
                    try:
                        await client.send_json(data)
                    except Exception:
                        disconnected.add(client)
                connected_clients.difference_update(disconnected)
            await asyncio.sleep(10)
    asyncio.create_task(stream_task())

async def fetch_set_data():
    try:
        response = requests.get("https://www.set.or.th/th/home", timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        symbol_cell = soup.find("td", class_="title-symbol", string=lambda x: "SET" in x if x else False)
        if not symbol_cell:
            return {"error": "symbol not found"}

        value = symbol_cell.find_next_sibling("td").span.text.strip()
        change = symbol_cell.find_next_siblings("td")[3].text.strip()
        number = value[-1] + change.split('.')[0][-1]
        return {"set": value, "value": change, "number": number}
    except Exception as e:
        return {"error": "fetch failed", "detail": str(e)}
