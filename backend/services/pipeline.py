"""
Pipeline orchestrator — runs all audio processing services per chunk.

Execution order:
  0. Resample to 16kHz
  1. Loudness analysis
  1.5 Sound Segregation — NMF splits chunk into up to 4 components
  2. Sound Classification — multi-label, runs on each component
  3. Distance Estimation
  4. Diarization  (if ANY component is speech)
  5. Transcription (if ANY component is speech)
"""

import os
from time import perf_counter

import numpy as np
from scipy import signal as scipy_signal

from services.diarization import diarize_speaker
from services.distance_estimator import estimate_distance
from services.loudness_analyzer import analyze_loudness
from services.sound_classifier import classify_sound
from services.sound_segregation import segregate_sounds
from services.transcription import transcribe_chunk
from utils.logger import get_logger

logger = get_logger(__name__)

TARGET_RATE = 16000  # Hz — all services require 16kHz
INPUT_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))  # Hz — actual input rate


def _resample_pcm(pcm_bytes: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample raw 16-bit mono PCM from src_rate to dst_rate."""
    if src_rate == dst_rate:
        return pcm_bytes
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    new_len = int(len(samples) * dst_rate / src_rate)
    resampled = scipy_signal.resample(samples, new_len)
    return resampled.astype(np.int16).tobytes()


def _merge_labels(component_results: list[dict]) -> dict:
    """
    Merge multi-label classification results from all NMF components.

    - Collects all labels across components (weighted by energy_ratio).
    - Picks the dominant label (highest weighted confidence) as the
      backward-compatible sound_type / sound_subtype.
    - Returns whether any component was classified as speech.
    """
    merged: dict[str, float] = {}   # label → best weighted confidence

    for comp_result in component_results:
        energy = comp_result["energy_ratio"]
        for lbl_entry in comp_result.get("labels", []):
            lbl = lbl_entry["sound_label"]
            weighted_conf = lbl_entry["confidence"] * energy
            if lbl not in merged or weighted_conf > merged[lbl]:
                merged[lbl] = weighted_conf

    if not merged:
        return {
            "labels": [{"sound_label": "silence", "sound_category": "silence", "confidence": 0.60}],
            "sound_type": "silence",
            "sound_subtype": None,
            "confidence": 0.60,
            "has_speech": False,
        }

    # Sort by weighted confidence
    sorted_labels = sorted(merged.items(), key=lambda x: x[1], reverse=True)

    # Re-look up category for each
    from services.sound_classifier import CATEGORY_MAP
    label_list = [
        {
            "sound_label":    lbl,
            "sound_category": CATEGORY_MAP.get(lbl, "unknown"),
            "confidence":     round(conf, 2),
        }
        for lbl, conf in sorted_labels
    ]

    dominant = label_list[0]
    dom_lbl = dominant["sound_label"]

    SUBTYPE_LABELS = {
        "fan", "ac", "engine", "traffic", "keyboard", "rain", "wind",
        "thunder", "cough", "sneeze", "clap", "dog_bark", "bird_song",
        "cat", "footsteps", "background_noise", "singing",
    }
    TYPE_LABELS = {"speech", "music", "silence"}

    if dom_lbl in TYPE_LABELS:
        sound_type, sound_subtype = dom_lbl, None
    elif dom_lbl in SUBTYPE_LABELS:
        sound_type = (
            dominant["sound_category"]
            if dominant["sound_category"] not in ("silence",)
            else "noise"
        )
        sound_subtype = dom_lbl
    else:
        sound_type, sound_subtype = "noise", dom_lbl

    has_speech = any(lbl == "speech" for lbl, _ in sorted_labels)

    return {
        "labels": label_list,
        "sound_type": sound_type,
        "sound_subtype": sound_subtype,
        "confidence": dominant["confidence"],
        "has_speech": has_speech,
    }


async def run_pipeline(
    pcm_bytes: bytes,
    session_id: str,
    chunk_index: int,
    timestamp_ms: int,
) -> dict:
    start_total = perf_counter()

    # ── Step 0: Resample to 16kHz if needed ──────────────────────────────
    if INPUT_RATE != TARGET_RATE:
        t_rs = perf_counter()
        pcm_bytes = _resample_pcm(pcm_bytes, INPUT_RATE, TARGET_RATE)
        logger.info(
            f"[Chunk {chunk_index}] Step 0 RESAMPLE: "
            f"{INPUT_RATE}Hz → {TARGET_RATE}Hz "
            f"({(perf_counter()-t_rs)*1000:.1f}ms)"
        )

    # ── Step 1: Loudness ─────────────────────────────────────────────────
    t0 = perf_counter()
    loudness = analyze_loudness(pcm_bytes)
    t1 = perf_counter()
    logger.info(
        f"[Chunk {chunk_index}] Step 1 LOUDNESS: "
        f"db={loudness['loudness_db']:.1f} label={loudness['loudness_label']} "
        f"({(t1-t0)*1000:.1f}ms)"
    )

    # ── Step 1.5: Sound Segregation (NMF) ────────────────────────────────
    t_seg0 = perf_counter()
    components = segregate_sounds(pcm_bytes, loudness["loudness_db"])
    t_seg1 = perf_counter()
    logger.info(
        f"[Chunk {chunk_index}] Step 1.5 SEGREGATION: "
        f"{len(components)} component(s) found ({(t_seg1-t_seg0)*1000:.1f}ms)"
    )

    # ── Step 2: Sound Classification (multi-label, per component) ────────
    t2_start = perf_counter()
    if components:
        # Classify each NMF component using its descriptor + PCM
        component_results = []
        for comp in components:
            result = classify_sound(
                pcm_bytes=comp["pcm_bytes"],
                loudness_db=loudness["loudness_db"],
                descriptor=comp["descriptor"],
            )
            result["energy_ratio"] = comp["energy_ratio"]
            component_results.append(result)
            logger.debug(
                f"[Chunk {chunk_index}] Component {comp['component_id']}: "
                f"energy={comp['energy_ratio']:.2f} → "
                f"{[l['sound_label'] for l in result['labels']]}"
            )
        sound = _merge_labels(component_results)
    else:
        # Chunk was silent / too short — classify the whole chunk directly
        raw_sound = classify_sound(pcm_bytes, loudness["loudness_db"])
        raw_sound["energy_ratio"] = 1.0
        sound = _merge_labels([raw_sound])

    t2 = perf_counter()
    all_labels = [l["sound_label"] for l in sound["labels"]]
    logger.info(
        f"[Chunk {chunk_index}] Step 2 SOUND: "
        f"type={sound['sound_type']} subtype={sound['sound_subtype']} "
        f"conf={sound['confidence']:.2f} labels={all_labels} "
        f"({(t2-t2_start)*1000:.1f}ms)"
    )

    # ── Step 3: Distance Estimation ───────────────────────────────────────
    distance = estimate_distance(loudness["loudness_db"], sound["sound_type"])
    t3 = perf_counter()
    logger.info(
        f"[Chunk {chunk_index}] Step 3 DISTANCE: "
        f"label={distance['distance_label']} conf={distance['distance_confidence']:.2f} "
        f"({(t3-t2)*1000:.1f}ms)"
    )

    # ── Steps 4 & 5: Diarization + Transcription ─────────────────────────
    # Triggered when ANY label in the chunk is "speech" (not just dominant)
    speaker_label = None
    speaker_confidence = None
    speaker_count = 0
    transcript = None
    transcript_confidence = None

    if sound["has_speech"]:
        logger.info(
            f"[Chunk {chunk_index}] Speech detected "
            f"(dominant={sound['sound_type']}, labels={all_labels})"
            " — running diarization + transcription"
        )

        diarization = diarize_speaker(session_id, pcm_bytes)
        speaker_label = diarization["speaker_label"]
        speaker_confidence = diarization["confidence"]
        speaker_count = diarization["speaker_count"]
        t4 = perf_counter()
        logger.info(
            f"[Chunk {chunk_index}] Step 4 DIARIZATION: "
            f"speaker={speaker_label} count={speaker_count} conf={speaker_confidence:.2f} "
            f"({(t4-t3)*1000:.1f}ms)"
        )

        transcription = await transcribe_chunk(pcm_bytes, "speech", session_id=session_id)
        transcript = transcription["transcript"]
        transcript_confidence = transcription["confidence"]
        t5 = perf_counter()
        logger.info(
            f"[Chunk {chunk_index}] Step 5 TRANSCRIPTION: "
            f"text={repr(transcript)} conf={transcript_confidence:.2f} "
            f"({(t5-t4)*1000:.1f}ms)"
        )
    else:
        logger.info(
            f"[Chunk {chunk_index}] No speech in labels={all_labels} "
            "→ skipping diarization and transcription"
        )
        t5 = t3

    # ── Audio features for debugging ──────────────────────────────────────
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    rms_intensity = float(np.sqrt(np.mean(samples ** 2))) / 32768.0 if samples.size > 0 else 0.0
    raw_features = {
        "sample_count": int(samples.size),
        "peak_amplitude": float(np.max(np.abs(samples))) if samples.size > 0 else 0.0,
        "mean_abs_amplitude": float(np.mean(np.abs(samples))) if samples.size > 0 else 0.0,
    }

    total_ms = (perf_counter() - start_total) * 1000
    logger.info(
        f"[Chunk {chunk_index}] ── Pipeline complete in {total_ms:.1f}ms "
        f"| speaker={speaker_label} | transcript={repr(transcript)} "
        f"| components={len(components)}"
    )

    return {
        "timestamp_ms": timestamp_ms,
        "speaker_label": speaker_label,
        "speaker_confidence": speaker_confidence,
        "speaker_count": speaker_count,
        # Backward-compatible flat fields
        "sound_type": sound["sound_type"],
        "sound_subtype": sound["sound_subtype"],
        "confidence": sound["confidence"],
        # NEW — full multi-label output
        "sound_labels": sound["labels"],
        "sound_components": len(components),
        # Transcription
        "transcript": transcript,
        "transcript_confidence": transcript_confidence,
        # Loudness / distance / intensity
        "loudness_db": loudness["loudness_db"],
        "loudness_label": loudness["loudness_label"],
        "distance_label": distance["distance_label"],
        "distance_confidence": distance["distance_confidence"],
        "audio_intensity_rms": round(rms_intensity, 6),
        "raw_audio_features": raw_features,
    }
