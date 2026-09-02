from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket
from browser_agent import handle_browser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {
        "status": "online",
        "agent": "Jacqueline"
    }


@app.get("/start")
def start_agent():
    return {
        "status": "ready",
        "agent": "Jacqueline"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    await handle_browser(websocket)