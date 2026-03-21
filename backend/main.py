import asyncio
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from database import init_db
from routers.sessions import router as sessions_router
from routers.websocket import router as websocket_router
from utils.logger import get_logger, setup_logging

load_dotenv()
setup_logging()

logger = get_logger(__name__)


def _prewarm_models() -> None:
    """
    Pre-load ML models in a background thread at startup.
    This prevents the 60-180s delay on the first WebSocket chunk.
    """
    logger.info("🔥 Pre-warming ML models in background thread…")

    # Warm up Whisper (only if Deepgram is not configured)
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not deepgram_key:
        try:
            from services.transcription import _check_whisper, _get_whisper_model
            if _check_whisper():
                logger.info("🔥 Warming up faster-whisper model (Deepgram not configured)…")
                _get_whisper_model()
                logger.info("✅ faster-whisper ready")
        except Exception as e:
            logger.warning(f"⚠️  faster-whisper warm-up skipped: {e}")
    else:
        logger.info(f"✅ Deepgram configured — skipping Whisper pre-warm")

    # Warm up pyannote (only if token configured)
    try:
        import services.diarization as _diar_mod
        from services.diarization import _check_pyannote, _get_pipeline
        if _check_pyannote():
            token = os.getenv("PYANNOTE_AUTH_TOKEN", "").strip()
            if token:
                logger.info("🔥 Warming up pyannote pipeline (30-90s on first run)…")
                # Reset any previous failure flag before trying
                _diar_mod._pyannote_load_failed = False
                _get_pipeline()
                logger.info("✅ pyannote ready")
            else:
                logger.warning("⚠️  PYANNOTE_AUTH_TOKEN not set — skipping pyannote warm-up")
    except Exception as e:
        import services.diarization as _diar_mod2
        _diar_mod2._pyannote_load_failed = False  # Don't block permanently from pre-warm failure
        logger.warning(f"⚠️  pyannote warm-up skipped: {e}")

    logger.info("🎉 Model pre-warming complete — server ready for audio streams")


@asynccontextmanager
async def lifespan(_: FastAPI):
    recordings_dir = os.getenv("RECORDINGS_DIR", "./recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    await init_db()
    logger.info("✅ Database initialized")

    lazy = os.getenv("DEV_LAZY_PREWARM", "false").lower() == "true"
    if lazy:
        # Non-blocking: models load in background, server accepts connections immediately
        t = threading.Thread(target=_prewarm_models, daemon=True)
        t.start()
        logger.info("🚀 Server accepting connections — models loading in background thread")
    else:
        # Blocking: 'Application startup complete' prints only after models are ready
        logger.info("⏳ Waiting for ML models to be ready before accepting connections…")
        await asyncio.get_event_loop().run_in_executor(None, _prewarm_models)
        logger.info("🚀 All models ready — server now accepting connections")

    yield


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Real-Time Audio Intelligence Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(websocket_router, tags=["websocket"])
