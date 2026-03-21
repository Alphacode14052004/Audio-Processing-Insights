import base64

import numpy as np


def decode_base64_audio(b64_string: str) -> bytes:
    if "," in b64_string and b64_string.lower().startswith("data:"):
        b64_string = b64_string.split(",", 1)[1]
    return base64.b64decode(b64_string)


def pcm_bytes_to_numpy(pcm_bytes: bytes) -> np.ndarray:
    if not pcm_bytes:
        return np.array([], dtype=np.float32)
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    return samples / 32768.0


def strip_wav_header(wav_bytes: bytes) -> bytes:
    if len(wav_bytes) >= 44 and wav_bytes[:4] == b"RIFF":
        return wav_bytes[44:]
    return wav_bytes


def compute_chunk_duration_ms(pcm_bytes: bytes, sample_rate: int = 16000) -> float:
    if not pcm_bytes:
        return 0.0
    total_samples = len(pcm_bytes) / 2
    return (total_samples / sample_rate) * 1000.0
