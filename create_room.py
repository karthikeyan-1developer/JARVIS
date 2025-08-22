from livekit import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(
    os.getenv("LIVEKIT_URL"),
    os.getenv("LIVEKIT_API_KEY"),
    os.getenv("LIVEKIT_API_SECRET"),
)

room = client.create_room("JarvisRoom")
print(f"Room created: {room.name}")
