"""
Real-time speech-to-text transcription service.

Primary:  Deepgram Nova-2 streaming WebSocket (real-time, per-session)
Fallback: faster-whisper with 3-second sliding audio buffer

Deepgram is used when DEEPGRAM_API_KEY is set in .env.
Audio flows: pipeline resamples to 16kHz → send to Deepgram → transcripts
arrive asynchronously → stored in per-session buffer → pipeline reads buffer.
"""

import os
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16000
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "").strip()

# ── Per-session state ─────────────────────────────────────────────────────
_dg_connections: dict = {}            # session_id → Deepgram WS connection
_transcript_buffers: dict = {}        # session_id → list[str] (received fragments)

# ── Whisper fallback state ─────────────────────────────────────────────────
_whisper_model = None
_whisper_available: Optional[bool] = None
_whisper_audio_buffers: dict[str, bytearray] = {}
_whisper_chunk_counts: dict[str, int] = {}
WHISPER_WINDOW_BYTES = 3 * SAMPLE_RATE * 2   # 3 seconds of 16kHz 16-bit audio


# ═══════════════════════════════════════════════════════════════════════════
#  Deepgram session management
# ═══════════════════════════════════════════════════════════════════════════


async def start_deepgram_session(session_id: str) -> bool:
    """
    Open a Deepgram streaming WebSocket for this session.
    Returns True if Deepgram is active, False if falling back to Whisper.
    """
    if not DEEPGRAM_API_KEY:
        logger.info(
            "DEEPGRAM_API_KEY not set — using faster-whisper fallback. "
            "Set DEEPGRAM_API_KEY in .env for real-time streaming."
        )
        return False

    try:
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        _transcript_buffers[session_id] = []
        dg_client = DeepgramClient(DEEPGRAM_API_KEY)
        connection = dg_client.listen.asyncwebsocket.v("1")

        # ── Transcript callback ───────────────────────────────────────────
        async def on_transcript(self, result, **kwargs):
            try:
                alt = result.channel.alternatives[0]
                text = alt.transcript.strip()
                if text and result.is_final:
                    _transcript_buffers.setdefault(session_id, []).append(text)
                    logger.info(f"[Deepgram] [{session_id[:8]}] 📝 {repr(text)}")
            except Exception:
                pass

        async def on_error(self, error, **kwargs):
            logger.error(f"[Deepgram] Error for session {session_id[:8]}: {error}")

        async def on_close(self, close, **kwargs):
            logger.info(f"[Deepgram] Connection closed for {session_id[:8]}")

        connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        connection.on(LiveTranscriptionEvents.Error, on_error)
        connection.on(LiveTranscriptionEvents.Close, on_close)

        # ── Connection options ────────────────────────────────────────────
        options = LiveOptions(
            model="nova-2",
            language="en",
            encoding="linear16",
            sample_rate=SAMPLE_RATE,
            channels=1,
            smart_format=True,
            punctuate=True,
            interim_results=False,   # final results only (more accurate)
            endpointing=500,         # ms of silence before utterance ends
        )

        started = await connection.start(options)
        if started:
            _dg_connections[session_id] = connection
            logger.info(f"✅ Deepgram Nova-2 streaming started for session {session_id[:8]}")
            return True
        else:
            logger.error(f"❌ Deepgram failed to start for session {session_id[:8]}")
            return False

    except ImportError:
        logger.warning(
            "deepgram-sdk not installed. Run: pip install deepgram-sdk. "
            "Falling back to faster-whisper."
        )
        return False
    except Exception as e:
        logger.error(f"❌ Deepgram session start failed: {e}")
        return False


async def send_audio_to_deepgram(session_id: str, pcm_bytes: bytes) -> None:
    """Stream 16kHz 16-bit mono PCM audio bytes to the Deepgram WebSocket."""
    conn = _dg_connections.get(session_id)
    if conn is None:
        return
    try:
        await conn.send(pcm_bytes)
    except Exception as e:
        logger.warning(f"[Deepgram] Send failed for {session_id[:8]}: {e}")


def get_latest_transcript(session_id: str) -> Optional[str]:
    """
    Pop and return all accumulated transcript fragments for this session.
    Returns None if no new transcripts have arrived since last call.
    """
    frags = _transcript_buffers.get(session_id, [])
    if not frags:
        return None
    text = " ".join(frags).strip()
    _transcript_buffers[session_id] = []      # clear after reading
    return text or None


async def stop_deepgram_session(session_id: str) -> None:
    """Close the Deepgram WebSocket and clean up all session state."""
    conn = _dg_connections.pop(session_id, None)
    if conn is not None:
        try:
            await conn.finish()
            logger.info(f"Deepgram session closed for {session_id[:8]}")
        except Exception as e:
            logger.debug(f"Deepgram close: {e}")

    _transcript_buffers.pop(session_id, None)
    _whisper_audio_buffers.pop(session_id, None)
    _whisper_chunk_counts.pop(session_id, None)


# ═══════════════════════════════════════════════════════════════════════════
#  Whisper fallback
# ═══════════════════════════════════════════════════════════════════════════


def _check_whisper() -> bool:
    global _whisper_available
    if _whisper_available is not None:
        return _whisper_available
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        _whisper_available = True
        logger.info("faster-whisper available as transcription fallback")
    except ImportError:
        _whisper_available = False
        logger.warning(
            "faster-whisper not installed — no transcription fallback. "
            "Run: pip install faster-whisper"
        )
    return _whisper_available


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    logger.info(f"⏳ Loading faster-whisper '{model_size}' (fallback)…")
    _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info("✅ faster-whisper fallback model loaded")
    return _whisper_model


def _transcribe_with_whisper(pcm_bytes: bytes, session_id: str) -> dict:
    """Transcribe using faster-whisper with a 3-second sliding audio buffer."""
    if not _check_whisper():
        return {"transcript": None, "confidence": 0.0}

    import numpy as np

    if session_id not in _whisper_audio_buffers:
        _whisper_audio_buffers[session_id] = bytearray()
        _whisper_chunk_counts[session_id] = 0

    _whisper_audio_buffers[session_id].extend(pcm_bytes)
    if len(_whisper_audio_buffers[session_id]) > WHISPER_WINDOW_BYTES:
        del _whisper_audio_buffers[session_id][:-WHISPER_WINDOW_BYTES]

    _whisper_chunk_counts[session_id] += 1
    buffer_s = len(_whisper_audio_buffers[session_id]) / (SAMPLE_RATE * 2)

    if _whisper_chunk_counts[session_id] % 2 != 0 and buffer_s < 1.0:
        return {"transcript": None, "confidence": 0.0}

    logger.info(f"[Whisper] Transcribing {buffer_s:.1f}s buffer for {session_id[:8]}…")

    try:
        model = _get_whisper_model()
        audio = (
            np.frombuffer(bytes(_whisper_audio_buffers[session_id]), dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        segments, _ = model.transcribe(
            audio, beam_size=3, language=None, vad_filter=False, word_timestamps=False
        )

        texts, total_logprob, count = [], 0.0, 0
        for seg in segments:
            t = seg.text.strip()
            if t:
                logger.debug(f"[Whisper] segment: {repr(t)}")
                texts.append(t)
                total_logprob += seg.avg_logprob
                count += 1

        if not texts:
            return {"transcript": None, "confidence": 0.0}

        transcript = " ".join(texts)
        avg_logprob = total_logprob / count if count > 0 else -1.0
        confidence = round(max(0.0, min(1.0, 1.0 + avg_logprob)), 3)
        logger.info(f"[Whisper] 📝 {repr(transcript)} (conf={confidence})")
        return {"transcript": transcript, "confidence": confidence}

    except Exception as e:
        logger.error(f"[Whisper] Transcription failed: {e}", exc_info=True)
        return {"transcript": None, "confidence": 0.0}


# ═══════════════════════════════════════════════════════════════════════════
#  Unified transcription interface (called by pipeline)
# ═══════════════════════════════════════════════════════════════════════════


async def transcribe_chunk(
    pcm_bytes: bytes,
    sound_type: str,
    session_id: str = "default",
) -> dict:
    """
    Transcribe a 16kHz 16-bit mono PCM audio chunk.

    If Deepgram is active for this session:
      → sends audio to Deepgram, returns latest received transcript
    If not (Deepgram unavailable or not configured):
      → uses faster-whisper with 3s accumulation buffer

    Args:
        pcm_bytes:  Raw PCM audio already resampled to 16kHz mono
        sound_type: From sound classifier ("speech", "silence", etc.)
        session_id: Session identifier

    Returns:
        {"transcript": str | None, "confidence": float}
    """
    if sound_type != "speech":
        return {"transcript": None, "confidence": 0.0}

    # ── Deepgram path ──────────────────────────────────────────────────────
    if session_id in _dg_connections:
        await send_audio_to_deepgram(session_id, pcm_bytes)
        transcript = get_latest_transcript(session_id)
        if transcript:
            logger.info(f"[Transcript] {session_id[:8]} → '{transcript}'")
        return {
            "transcript": transcript,
            "confidence": 0.92 if transcript else 0.0,
        }

    # ── Whisper fallback path ──────────────────────────────────────────────
    return _transcribe_with_whisper(pcm_bytes, session_id)
