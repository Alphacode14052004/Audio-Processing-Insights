import json
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import Insight, RecordingSession, SessionStatus
from routers.sessions import finalize_session
from schemas import SessionStopResponse
from services.audio_assembler import audio_assembler
from services.pipeline import run_pipeline
from utils.audio_utils import decode_base64_audio, strip_wav_header
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

MAX_RECORDING_DURATION_SECONDS = int(os.getenv("MAX_RECORDING_DURATION_SECONDS", "3600"))


def _decode_binary_chunk(payload: bytes) -> bytes:
    try:
        text_payload = payload.decode("utf-8")
        return decode_base64_audio(text_payload)
    except Exception:
        return payload


@router.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    first_chunk = True
    chunk_index = 0

    async def send_error(message: str, fatal: bool = False) -> None:
        await websocket.send_json({"type": "error", "message": message, "fatal": fatal})

    try:
        async with AsyncSessionLocal() as db:
            session = await db.get(RecordingSession, session_id)
            if not session or session.status != SessionStatus.recording:
                await websocket.close(code=4004)
                return

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                try:
                    pcm_chunk = _decode_binary_chunk(message["bytes"])
                    if first_chunk:
                        pcm_chunk = strip_wav_header(pcm_chunk)
                        first_chunk = False

                    timestamp_ms = int(audio_assembler.get_duration_ms(session_id))
                    audio_assembler.append_chunk(session_id, pcm_chunk)

                    async with AsyncSessionLocal() as db:
                        session = await db.get(RecordingSession, session_id)
                        if not session:
                            await send_error("session not found", fatal=True)
                            await websocket.close(code=4004)
                            return

                        insight_payload = await run_pipeline(
                            pcm_bytes=pcm_chunk,
                            session_id=session_id,
                            chunk_index=chunk_index,
                            timestamp_ms=timestamp_ms,
                        )
                        insight = Insight(session_id=session_id, **insight_payload)
                        db.add(insight)
                        await db.commit()
                        await db.refresh(insight)

                    await websocket.send_json(
                        {
                            "type": "insight",
                            "data": {
                                "insight_id": insight.id,
                                "timestamp_ms": insight.timestamp_ms,
                                "speaker_label": insight.speaker_label,
                                "sound_type": insight.sound_type,
                                "sound_subtype": insight.sound_subtype,
                                "transcript": insight.transcript,
                                "loudness_db": insight.loudness_db,
                                "loudness_label": insight.loudness_label,
                                "distance_label": insight.distance_label,
                                "distance_confidence": insight.distance_confidence,
                            },
                        }
                    )

                    chunk_index += 1
                    if audio_assembler.get_duration_ms(session_id) / 1000.0 > MAX_RECORDING_DURATION_SECONDS:
                        await send_error("max recording duration reached", fatal=False)

                except Exception as chunk_error:
                    logger.exception(
                        "Chunk processing failed",
                        extra={"session_id": session_id, "error": str(chunk_error)},
                    )
                    await send_error("chunk processing failed", fatal=False)
                continue

            text_payload = message.get("text")
            if text_payload is None:
                continue

            try:
                event = json.loads(text_payload)
            except json.JSONDecodeError:
                await send_error("invalid JSON message", fatal=False)
                continue

            event_type = event.get("type")
            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if event_type == "stop":
                async with AsyncSessionLocal() as db:
                    session = await db.get(RecordingSession, session_id)
                    if not session:
                        await send_error("session not found", fatal=True)
                        await websocket.close(code=4004)
                        return

                    stop_result: SessionStopResponse = await finalize_session(db, session)

                await websocket.send_json(
                    {
                        "type": "session_complete",
                        "data": stop_result.model_dump(mode="json"),
                    }
                )
                await websocket.close()
                return

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"session_id": session_id})
    except Exception as ws_error:
        logger.exception(
            "WebSocket failure",
            extra={"session_id": session_id, "error": str(ws_error)},
        )
    finally:
        audio_assembler.clear(session_id)
