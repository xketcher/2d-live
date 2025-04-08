from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, status
from bs4 import BeautifulSoup
from typing import Set, Optional
import aiohttp, asyncio

app = FastAPI()
clients: Set[WebSocket] = set()
is_running = False

API_TOKEN = "zuA95eBBJZoWzsqlNQQKxgnmCM6kmgwsZbZFoSE"
WS_TOKEN = "uwfHwIbn5rVHWWjEHeQKlM7VNMJC9LUggdJBvbQHw7dc"

# Dependency to check API token
async def verify_api_token(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")

# Dependency to check WS token for WebSocket connections
async def verify_ws_token(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {WS_TOKEN}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid WebSocket token")

@app.get("/ping", dependencies=[Depends(verify_api_token)])
async def ping(): 
    return {"status": "ok"}

@app.get("/start", dependencies=[Depends(verify_api_token)])
async def start(): 
    global is_running
    is_running = True
    return {"status": "started"}

@app.get("/stop", dependencies=[Depends(verify_api_token)])
async def stop(): 
    global is_running
    is_running = False
    return {"status": "stopped"}

@app.get("/get", dependencies=[Depends(verify_api_token)])
async def get(): 
    return await fetch_set_data()

@app.post("/send", dependencies=[Depends(verify_api_token)])
async def send(data: dict):
    global is_running
    is_running = False
    await broadcast(data)
    return {"status": "sent", "connected": len(clients)}

@app.websocket("/ws")
async def websocket(ws: WebSocket, authorization: str = Depends(verify_ws_token)):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)

@app.on_event("startup")
async def startup():
    asyncio.create_task(stream_task())

async def stream_task():
    while True:
        if is_running:
            data = await fetch_set_data()
            await broadcast(data)
        await asyncio.sleep(10)

async def broadcast(data: dict):
    disconnected = set()
    for ws in clients:
        try:
            await ws.send_json(data)
        except:
            disconnected.add(ws)
    clients.difference_update(disconnected)

async def fetch_set_data():
    url = "https://www.set.or.th/th/home"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td", class_="title-symbol", string=lambda x: "SET" in x if x else False)
        if not cell:
            return {"error": "symbol not found"}
        value = cell.find_next_sibling("td").span.text.strip()
        change = cell.find_next_siblings("td")[3].text.strip()
        return {
            "set": value,
            "value": change,
            "number": value[-1] + change.split('.')[0][-1]
        }
    except Exception as e:
        return {"error": "fetch failed", "detail": str(e)}
