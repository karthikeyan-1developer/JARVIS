import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from livekit import api
from pydantic import BaseModel

load_dotenv()

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")

if not (LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL):
    raise RuntimeError("Missing LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in environment")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenResponse(BaseModel):
    url: str
    token: str

@app.get("/token", response_model=TokenResponse)
def get_token(
    room: str = Query(..., description="Room name"),
    identity: str = Query(..., description="User identity")
):
    grants = api.VideoGrants(
        room_join=True,
        can_publish=True,
        can_subscribe=True,
        room=room,
    )
    at = api.AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
    at.add_grant(grants)
    at.with_identity(identity)
    token = at.to_jwt()
    return TokenResponse(url=LIVEKIT_URL, token=token)
