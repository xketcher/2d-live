from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
import requests
from bs4 import BeautifulSoup

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
        await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        async with clients_lock:
            clients.discard(websocket)

async def broadcast_numbers():
    while True:
        await broadcast_event.wait()
        if broadcasting:
            try:
                url = "https://www.set.or.th/th/home"
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.content, "html.parser")

                # Find the SET value
                set_td = soup.find("td", class_="title-symbol", string=lambda text: text and "SET" in text)
                set_value = None
                value_col = None

                if set_td:
                    value_td = set_td.find_next_sibling("td")
                    if value_td:
                        span = value_td.find("span")
                        if span:
                            set_value = span.get_text(strip=True)

                    # The 5th following sibling (index 3) for value column
                    value_td_list = set_td.find_next_siblings("td")
                    if len(value_td_list) >= 4:
                        value_col = value_td_list[3].get_text(strip=True)

                last_digit_set = set_value[-1] if set_value else ""
                digit_before_decimal = value_col.split('.')[0][-1] if value_col and '.' in value_col else ""

                number = last_digit_set + digit_before_decimal
                message = {
                    "set": set_value,
                    "value": value_col,
                    "number": number
                }

                async with clients_lock:
                    disconnected = set()
                    for client in clients:
                        try:
                            await client.send_json(message)
                        except:
                            disconnected.add(client)
                    clients.difference_update(disconnected)

            except Exception as e:
                print("Scraping error:", str(e))

        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_numbers())
