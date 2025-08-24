from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os, random, string

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Global game state
lobby = None
connections = []  # active WebSocket connections

def generate_lobby_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def broadcast_lobby():
    """Send updated lobby slots to all connected clients"""
    global lobby
    if not lobby:
        return
    for conn in list(connections):
        try:
            await conn.send_json({"event": "lobby_update", "slots": lobby["slots"]})
        except:
            connections.remove(conn)

@app.get("/")
def read_index():
    return FileResponse(os.path.join("frontend", "index.html"))

@app.get("/lobby.html")
def read_lobby():
    return FileResponse(os.path.join("frontend", "lobby.html"))

@app.get("/game.html")
def read_game():
    return FileResponse(os.path.join("frontend", "game.html"))

@app.post("/api/create_lobby")
async def create_lobby(name: str = Query("Host")):
    global lobby
    code = generate_lobby_code()
    lobby = {"code": code, "slots": [None] * 2}
    lobby["slots"][0] = {"name": name, "role": "host"}
    await broadcast_lobby()
    return {"code": code, "slots": lobby["slots"]}

@app.post("/api/join_lobby/{code}")
async def join_lobby(code: str, name: str = Query("Player")):
    global lobby
    if not lobby or lobby["code"] != code:
        return {"error": "Lobby not found"}
    for i in range(2):
        if lobby["slots"][i] is None:
            lobby["slots"][i] = {"name": name, "role": "player"}
            await broadcast_lobby()
            return {"code": code, "slots": lobby["slots"]}
    return {"error": "Lobby full"}

@app.post("/api/start_game/{code}")
async def start_game(code: str):
    global lobby
    if not lobby or lobby["code"] != code:
        return {"error": "Lobby not found"}
    if any(slot is None for slot in lobby["slots"]):
        return {"error": "Not enough players"}
    # Broadcast start event
    for conn in list(connections):
        try:
            await conn.send_json({"event": "start_game", "redirect": "/game.html"})
        except:
            connections.remove(conn)
    return {"status": "game started"}

@app.websocket("/ws/lobby/{code}")
async def websocket_lobby(websocket: WebSocket, code: str):
    await websocket.accept()
    connections.append(websocket)
    try:
        if lobby and lobby["code"] == code:
            await websocket.send_json({"event": "lobby_update", "slots": lobby["slots"]})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.remove(websocket)
