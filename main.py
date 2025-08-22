from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent import get_jarvis_response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = {}  # dict[str, list[WebSocket]]


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()

    if room_id not in rooms:
        rooms[room_id] = []
    rooms[room_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            # Broadcast user message to others (optional)
            for conn in rooms[room_id]:
                if conn is not websocket:
                    await conn.send_text(f"User: {data}")

            # Get Jarvis reply
            jarvis_reply = await get_jarvis_response(data)

            # Send to everyone (including sender)
            for conn in rooms[room_id]:
                await conn.send_text(jarvis_reply)

    except WebSocketDisconnect:
        # Cleanup on disconnect
        if room_id in rooms and websocket in rooms[room_id]:
            rooms[room_id].remove(websocket)
            if not rooms[room_id]:
                del rooms[room_id]
