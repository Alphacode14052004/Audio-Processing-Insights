"""
Speaker diarization service.

Strategy:
- PRIMARY: pyannote.audio 3.1 (requires torch + HF token)
  → Uses a 5-second sliding window for reliable speaker identification
- FALLBACK: Energy + pause-based speaker tracking (no ML needed)
  → Detects speaker changes based on silence gaps between speech turns

The fallback activates automatically if pyannote/torch are not installed
OR if pyannote fails for any reason (token issues, loading errors, etc.).
"""

import io
import os
import wave
from threading import Lock

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # bytes per sample (16-bit PCM)
CHANNELS = 1
WINDOW_SECONDS = int(os.getenv("DIARIZATION_WINDOW_SECONDS", "5"))
WINDOW_BYTES = WINDOW_SECONDS * SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS

# ── Singleton pyannote pipeline (lazy-loaded) ────────────────────────────
_pipeline = None
_pipeline_lock = Lock()
_pyannote_available = None   # None=untested, True/False after first check
_pyannote_load_failed = False  # If load fails once, skip forever


# ── Per-session state ─────────────────────────────────────────────────────
_session_buffers: dict[str, bytearray] = {}
_session_speakers: dict[str, dict] = {}


def _check_pyannote() -> bool:
    """Check once if pyannote and torch are importable."""
    global _pyannote_available
    if _pyannote_available is not None:
        return _pyannote_available
    try:
        import torch  # noqa: F401
        import torchaudio  # noqa: F401
        from pyannote.audio import Pipeline  # noqa: F401
        _pyannote_available = True
        logger.info("✅ pyannote.audio detected — real diarization will be used")
    except ImportError as e:
        _pyannote_available = False
        logger.warning(
            f"⚠️  pyannote.audio/torch not installed ({e}). "
            "Using energy-based speaker fallback. "
            "To enable real diarization run:\n"
            "  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu\n"
            "  pip install pyannote.audio"
        )
    return _pyannote_available


def _get_pipeline():
    """Lazy-load the pyannote diarization pipeline (one-time cost)."""
    global _pipeline, _pyannote_load_failed

    if _pipeline is not None:
        return _pipeline

    if _pyannote_load_failed:
        raise RuntimeError("pyannote pipeline previously failed to load — using fallback")

    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline

        token = os.getenv("PYANNOTE_AUTH_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "PYANNOTE_AUTH_TOKEN not set in .env — "
                "required for pyannote.audio"
            )

        logger.info("⏳ Loading pyannote/speaker-diarization-3.1 from HuggingFace…")
        logger.info("   (First load downloads ~200MB — this is a one-time cost)")

        from pyannote.audio import Pipeline

        try:
            # ── NEW API (pyannote.audio >= 3.1) uses `token=`, not `use_auth_token=`
            _pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token,
            )
            logger.info("✅ pyannote pipeline loaded successfully")
        except TypeError:
            # Older pyannote version fallback
            logger.warning("Falling back to use_auth_token= API (older pyannote)")
            _pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token,
            )
            logger.info("✅ pyannote pipeline loaded (legacy API)")

        return _pipeline


def _pcm_to_wav_buffer(pcm_bytes: bytes) -> io.BytesIO:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    buf.seek(0)
    return buf


def _run_pyannote(session_id: str, window_pcm: bytes) -> dict:
    """Run pyannote diarization on the accumulated audio window."""
    import torchaudio

    logger.info(
        f"🔍 Running pyannote on {len(window_pcm)/16000/2:.1f}s of audio "
        f"for session {session_id[:8]}…"
    )

    pipeline = _get_pipeline()
    wav_buf = _pcm_to_wav_buffer(window_pcm)
    waveform, sr = torchaudio.load(wav_buf)
    if sr != SAMPLE_RATE:
        waveform = torchaudio.functional.resample(waveform, sr, SAMPLE_RATE)

    result = pipeline({"waveform": waveform, "sample_rate": SAMPLE_RATE})

    # Resolve Annotation from whatever pyannote returns:
    # - pyannote <= 3.2: returns Annotation directly (has .itertracks)
    # - pyannote 3.3+:  returns DiarizeOutput NamedTuple — try attribute then index
    if hasattr(result, "itertracks"):
        annotation = result
    elif hasattr(result, "diarization") and hasattr(result.diarization, "itertracks"):
        annotation = result.diarization
    elif hasattr(result, "__getitem__"):
        # DiarizeOutput is a NamedTuple — first element is the Annotation
        annotation = result[0]
    else:
        annotation = result

    speakers_seen: set[str] = set()
    last_speaker = None

    for turn, _, speaker in annotation.itertracks(yield_label=True):
        speakers_seen.add(speaker)
        last_speaker = speaker

    speaker_count = len(speakers_seen)

    if last_speaker is None:
        logger.info("pyannote found no speech segments in window")
        return {"speaker_label": None, "confidence": 0.0, "speaker_count": 0}

    sorted_speakers = sorted(speakers_seen)
    speaker_index = sorted_speakers.index(last_speaker)
    speaker_label = f"Speaker {speaker_index + 1}"

    logger.info(
        f"✅ pyannote result: {speaker_label} "
        f"(unique speakers so far: {sorted_speakers})"
    )

    return {
        "speaker_label": speaker_label,
        "confidence": 0.82,
        "speaker_count": speaker_count,
    }


def _run_energy_fallback(session_id: str, pcm_bytes: bytes) -> dict:
    """
    Energy + silence-gap based speaker change detection.

    Heuristic: after a silent gap, the next speech chunk is likely a new
    speaker turn. Cycles through up to 3 speakers.

    This is a FALLBACK — install pyannote for real diarization.
    """
    state = _session_speakers.setdefault(session_id, {
        "current_speaker_idx": 0,
        "total_speakers_seen": 1,
        "prev_was_silent": False,
        "chunks_in_turn": 0,
    })

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(samples ** 2))) if samples.size > 0 else 0.0
    is_silent = rms < 0.008

    if is_silent:
        state["prev_was_silent"] = True
        state["chunks_in_turn"] = 0
        idx = state["current_speaker_idx"]
        logger.debug(f"[Fallback] Silence gap — holding Speaker {idx + 1}")
    else:
        if state["prev_was_silent"] and state["chunks_in_turn"] == 0:
            # Crossed a silence boundary → likely new speaker turn
            state["current_speaker_idx"] = (state["current_speaker_idx"] + 1) % 3
            state["total_speakers_seen"] = max(
                state["total_speakers_seen"],
                state["current_speaker_idx"] + 1
            )
            logger.info(
                f"[Fallback] Speaker change detected → "
                f"Speaker {state['current_speaker_idx'] + 1} "
                f"(rms_pre_turn={rms:.4f})"
            )
        idx = state["current_speaker_idx"]
        state["prev_was_silent"] = False
        state["chunks_in_turn"] += 1

    speaker_label = f"Speaker {idx + 1}"
    speaker_count = state["total_speakers_seen"]

    return {
        "speaker_label": speaker_label,
        "confidence": 0.55,  # lower since this is heuristic
        "speaker_count": speaker_count,
    }


def diarize_speaker(session_id: str, pcm_bytes: bytes) -> dict:
    """
    Identify which speaker is speaking in this audio chunk.

    Tries pyannote.audio first (real ML). Falls back to energy-based
    speaker change detection if pyannote is unavailable or fails.

    Returns:
        {"speaker_label": str | None, "confidence": float, "speaker_count": int}
    """
    global _pyannote_load_failed

    # Accumulate sliding window for pyannote
    if session_id not in _session_buffers:
        _session_buffers[session_id] = bytearray()
    _session_buffers[session_id].extend(pcm_bytes)
    if len(_session_buffers[session_id]) > WINDOW_BYTES:
        del _session_buffers[session_id][:-WINDOW_BYTES]

    # Choose strategy
    if _check_pyannote() and not _pyannote_load_failed:
        window_pcm = bytes(_session_buffers[session_id])
        window_duration = len(window_pcm) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
        if window_duration < 1.0:
            logger.debug(
                f"[Diarization] Only {window_duration:.2f}s accumulated — "
                "need 1s minimum, using fallback for now"
            )
            return _run_energy_fallback(session_id, pcm_bytes)
        try:
            return _run_pyannote(session_id, window_pcm)
        except Exception as e:
            _pyannote_load_failed = True
            logger.error(
                f"❌ pyannote failed: {e}. "
                "Permanently switching to energy-based fallback for this session.",
                exc_info=True
            )
            return _run_energy_fallback(session_id, pcm_bytes)
    else:
        return _run_energy_fallback(session_id, pcm_bytes)


def clear_session_buffer(session_id: str) -> None:
    """Free per-session state when a session ends."""
    _session_buffers.pop(session_id, None)
    _session_speakers.pop(session_id, None)
