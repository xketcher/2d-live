from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
from typing import Dict, Set
from bs4 import BeautifulSoup
from datetime import datetime
import pytz, aiohttp, asyncio

app = FastAPI()

rooms: Dict[str, Set[WebSocket]] = {}
is_running = False
session: aiohttp.ClientSession = None

API_TOKEN = "zuA95eBBJZoWzsqlNQQKxgnmCM6kmgwsZbZFoSE"
WS_TOKEN = "uwfHwIbn5rVHWWjEHeQKlM7VNMJC9LUggdJBvbQHw7dc"
ALLOWED_ROOMS = {"live", "chat"}

def auth_check(token: str, expected: str):
    if token != f"Bearer {expected}":
        raise HTTPException(401, "Invalid token")

@app.get("/ping")
def ping(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    return {"ok": True}

@app.get("/dashboard")
def dashboard(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    return {
        "live_total_client": len(rooms.get("live", [])),
        "chat_total_client": len(rooms.get("chat", [])),
        "server_status": "running" if is_running else "stopped"
    }

@app.get("/start")
def start(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    global is_running
    is_running = True
    return {"status": "started"}

@app.get("/stop")
def stop(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    global is_running
    is_running = False
    return {"status": "stopped"}

@app.get("/status")
def status(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    return {"status": "running" if is_running else "stopped"}

@app.get("/get")
async def get(Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    return await fetch_set_data()

@app.post("/send/{room}")
async def send(room: str, data: dict, Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    global is_running
    is_running = False
    return {"sent": await broadcast(room, data)}

@app.get("/total_client/{room}")
def total(room: str, Authorization: str = Header()):
    auth_check(Authorization, API_TOKEN)
    return {"room": room, "clients": len(rooms.get(room, []))}

@app.websocket("/ws/{room}")
async def ws(ws: WebSocket, room: str, Authorization: str = Header()):
    auth_check(Authorization, WS_TOKEN)
    if room not in ALLOWED_ROOMS:
        await ws.close(code=1008)
        return
    await ws.accept()
    rooms.setdefault(room, set()).add(ws)
    try:
        while True:
            await ws.receive()
    except WebSocketDisconnect:
        pass
    finally:
        rooms[room].discard(ws)
        if not rooms[room]:
            del rooms[room]

@app.on_event("startup")
async def on_start():
    global session
    session = aiohttp.ClientSession()
    asyncio.create_task(live_push())

@app.on_event("shutdown")
async def on_shutdown():
    await session.close()

async def live_push():
    while True:
        if is_running:
            data = await fetch_set_data()
            await broadcast("live", data)
        await asyncio.sleep(10)

async def broadcast(room: str, data: dict):
    conns = rooms.get(room, set()).copy()
    count = 0
    for ws in conns:
        try:
            await ws.send_json(data)
            count += 1
        except:
            rooms[room].discard(ws)
    return count

async def fetch_set_data():
    try:
        async with session.get("https://www.set.or.th/th/home", timeout=10) as r:
            html = await r.text()
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td", class_="title-symbol", string=lambda x: "SET" in x if x else False)
        val = cell.find_next_sibling("td").span.text.strip()
        chg = cell.find_next_siblings("td")[3].text.strip()

        now = datetime.now(pytz.timezone("Asia/Yangon"))
        dt = now.strftime("%Y-%m-%d %I:%M:%S %p")

        hour = now.hour
        minute = now.minute
        if (hour == 12 and minute <= 5) or (hour < 12) or (hour == 16 and minute >= 36) or (hour > 16):
            type_val = "12:01 PM"
        else:
            type_val = "04:30 PM"

        return {
            "set": val,
            "value": chg,
            "twod": val[-1] + chg.split('.')[0][-1],
            "date": dt,
            "type": type_val
        }
    except Exception as e:
        return {"error": str(e)}
