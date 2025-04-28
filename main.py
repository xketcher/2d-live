from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, status
from bs4 import BeautifulSoup
from typing import Set, Optional
import aiohttp, asyncio

app = FastAPI()
clients: Set[WebSocket] = set()
is_running = False

API_TOKEN = "zuA95eBBJZoWzsqlNQQKxgnmCM6kmgwsZbZFoSE"
WS_TOKEN = "uwfHwIbn5rVHWWjEHeQKlM7VNMJC9LUggdJBvbQHw7dc"

async def verify_token(header: Optional[str], token: str):
    if header != f"Bearer {token}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@app.get("/ping")
async def ping(auth: str = Header(None, alias="Authorization")):
    await verify_token(auth, API_TOKEN)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Server is running!"}

@app.get("/start")
async def start(auth: str = Header(None, alias="Authorization")):
    await verify_token(auth, API_TOKEN)
    global is_running
    is_running = True
    return {"status": "started"}

@app.get("/stop")
async def stop(auth: str = Header(None, alias="Authorization")):
    await verify_token(auth, API_TOKEN)
    global is_running
    is_running = False
    return {"status": "stopped"}

@app.get("/get")
async def get(auth: str = Header(None, alias="Authorization")):
    await verify_token(auth, API_TOKEN)
    return await fetch_set_data()

@app.post("/send")
async def send(data: dict, auth: str = Header(None, alias="Authorization")):
    await verify_token(auth, API_TOKEN)
    global is_running
    is_running = False
    await broadcast(data)
    return {"status": "sent", "connected": len(clients)}

@app.websocket("/ws")
async def websocket(ws: WebSocket, authorization: str = Header(None, alias="Authorization")):
    await verify_token(authorization, WS_TOKEN)
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
    for ws in clients.copy():
        try:
            await ws.send_json(data)
        except:
            clients.discard(ws)

async def fetch_set_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.set.or.th/th/home", timeout=10) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td", class_="title-symbol", string=lambda x: "SET" in x if x else False)
        if not cell: return {"error": "symbol not found"}
        value = cell.find_next_sibling("td").span.text.strip()
        change = cell.find_next_siblings("td")[3].text.strip()
        return {
            "set": value,
            "value": change,
            "number": value[-1] + change.split('.')[0][-1]
        }
    except Exception as e:
        return {"error": "fetch failed", "detail": str(e)}
