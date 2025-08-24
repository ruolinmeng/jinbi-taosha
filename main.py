from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os, random, string
from fastapi import Form

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Player data structure
class Player:
    def __init__(self, name, role="player"):
        self.name = name
        self.role = role  # "host" or "player"
        self.hp = 10
        self.attributes = {
            "strength": 0,  # 武力
            "speed": 0,     # 速度
            "capacity": 0   # 负重
        }
        self.ready = False  # Whether attributes have been set

# Lobby structure
lobby = {
    "code": None,
    "slots": [None] * 2,  # adjust for max players
    "players": {}  # player_name -> Player object
}

# Global game state
# lobby = None
connections = []  # active WebSocket connections

@app.post("/api/set_attributes/{code}/{name}")
async def set_attributes(
    code: str,
    name: str,
    strength: int = Form(...),
    speed: int = Form(...),
    capacity: int = Form(...)
):
    global lobby
    if not lobby or lobby["code"] != code:
        return {"error": "Lobby not found"}
    if name not in lobby["players"]:
        return {"error": "Player not found"}

    total = strength + speed + capacity
    if total != 10:
        return {"error": "Attributes must sum to 10"}

    player = lobby["players"][name]
    player.attributes["strength"] = strength
    player.attributes["speed"] = speed
    player.attributes["capacity"] = capacity
    player.ready = True

    return {"status": "ok"}

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

@app.get("/attributes.html")
def read_attributes():
    return FileResponse(os.path.join("frontend", "attributes.html"))

# when creating lobby
@app.post("/api/create_lobby")
async def create_lobby(name: str = Query("Host")):
    global lobby
    code = generate_lobby_code()
    lobby = {
        "code": code,
        "slots": [None] * 2,
        "players": {}
    }
    # register host as player object
    lobby["slots"][0] = {"name": name, "role": "host"}
    lobby["players"][name] = Player(name, role="host")
    await broadcast_lobby()
    return {"code": code, "slots": lobby["slots"]}


# when joining lobby
@app.post("/api/join_lobby/{code}")
async def join_lobby(code: str, name: str = Query("Player")):
    global lobby
    if not lobby or lobby["code"] != code:
        return {"error": "Lobby not found"}
    for i in range(len(lobby["slots"])):
        if lobby["slots"][i] is None:
            lobby["slots"][i] = {"name": name, "role": "player"}
            lobby["players"][name] = Player(name, role="player")
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
    
    # Broadcast "start game" event, but send players to attributes.html instead of game.html
    for conn in list(connections):
        try:
            await conn.send_json({
                "event": "start_game",
                "redirect": "/attributes.html"
            })
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
