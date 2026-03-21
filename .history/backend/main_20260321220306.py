import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from database import init_db
from routers.sessions import router as sessions_router
from routers.websocket import router as websocket_router
from utils.logger import setup_logging

load_dotenv()
setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    recordings_dir = os.getenv("RECORDINGS_DIR", "./recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="Real-Time Audio Intelligence Backend", version="1.0.0", lifespan=lifespan)


@app.get("/")
@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(websocket_router, tags=["websocket"])
