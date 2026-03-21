import numpy as np


def analyze_loudness(pcm_bytes: bytes) -> dict:
    if not pcm_bytes:
        return {"loudness_db": -100.0, "loudness_label": "silence"}

    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size == 0:
        return {"loudness_db": -100.0, "loudness_label": "silence"}

    rms = float(np.sqrt(np.mean(np.square(audio))))
    loudness_db = float(20.0 * np.log10(rms + 1e-10))

    if loudness_db > -10:
        label = "very_loud"
    elif loudness_db > -20:
        label = "loud"
    elif loudness_db > -35:
        label = "moderate"
    elif loudness_db > -50:
        label = "quiet"
    else:
        label = "silence"

    return {"loudness_db": loudness_db, "loudness_label": label}
