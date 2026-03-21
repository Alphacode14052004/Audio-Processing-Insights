"""
Sound Categorization — Milestone 5
Multi-label sound classifier with broad category grouping.

Classifies each audio component (or full chunk) into one or more
sound labels and groups them into high-level categories:
  natural        — rain, wind, breeze, thunder
  artificial     — fan, AC, engine, traffic, keyboard, machinery
  human_activity — speech, cough, sneeze, clap, footsteps
  music          — singing, instruments, background music
  animal         — dog barking, bird singing, cat

Accepts either:
  (a) raw PCM bytes  — classifies the whole chunk
  (b) a pre-built features dict from segregate_sounds descriptor  — skips re-extraction

Uses only numpy + scipy — no model download needed.
Same public function name as the original: classify_sound()
"""

import numpy as np
from scipy import signal as scipy_signal

from utils.logger import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16000

# ── Category taxonomy ────────────────────────────────────────────────────────
CATEGORY_MAP: dict[str, str] = {
    # natural
    "rain":         "natural",
    "wind":         "natural",
    "breeze":       "natural",
    "thunder":      "natural",
    "water":        "natural",
    # artificial
    "fan":          "artificial",
    "ac":           "artificial",
    "engine":       "artificial",
    "traffic":      "artificial",
    "keyboard":     "artificial",
    "machinery":    "artificial",
    # human activity
    "speech":       "human_activity",
    "cough":        "human_activity",
    "sneeze":       "human_activity",
    "clap":         "human_activity",
    "footsteps":    "human_activity",
    # music
    "music":        "music",
    "singing":      "music",
    # animal
    "dog_bark":     "animal",
    "bird_song":    "animal",
    "cat":          "animal",
    # fallback
    "background_noise": "artificial",
    "silence":      "silence",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_mono_float(pcm_bytes: bytes) -> np.ndarray:
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size == 0:
        return np.array([], dtype=np.float32)
    return samples.astype(np.float32) / 32768.0


def _compute_features(pcm_bytes: bytes, loudness_db: float) -> dict:
    """
    Extract spectral + temporal features from raw PCM bytes.
    Returns a flat dict compatible with the descriptor format produced
    by segregate_sounds(), so both paths share the same rule engine.
    """
    samples = _to_mono_float(pcm_bytes)

    if samples.size < 2:
        return {
            "rms_energy": 0.0, "zcr": 0.0,
            "spectral_centroid": 0.0, "spectral_rolloff": 0.0,
            "spectral_bandwidth": 0.0, "energy_variance": 0.0,
            "low_band_ratio": 0.0, "mid_band_ratio": 0.0,
            "high_band_ratio": 0.0, "harmonic_ratio": 0.0,
            "attack_rate": 0.0, "is_empty": True,
        }

    rms_energy = float(np.sqrt(np.mean(samples ** 2)))

    # Zero-crossing rate
    signs = np.sign(samples)
    zcr = float(np.mean(np.abs(np.diff(signs)) > 0))

    # Welch PSD
    n_fft = min(1024, len(samples))
    freqs, psd = scipy_signal.welch(
        samples, fs=SAMPLE_RATE, nperseg=n_fft,
        noverlap=n_fft // 2, scaling="spectrum",
    )
    psd_sum = float(np.sum(psd))

    if psd_sum < 1e-12:
        return {
            "rms_energy": rms_energy, "zcr": zcr,
            "spectral_centroid": 0.0, "spectral_rolloff": 0.0,
            "spectral_bandwidth": 0.0, "energy_variance": 0.0,
            "low_band_ratio": 0.0, "mid_band_ratio": 0.0,
            "high_band_ratio": 0.0, "harmonic_ratio": 0.0,
            "attack_rate": 0.0, "is_empty": rms_energy < 0.001,
        }

    spectral_centroid = float(np.sum(freqs * psd) / psd_sum)

    cumsum = np.cumsum(psd)
    rolloff_idx = np.searchsorted(cumsum, 0.85 * psd_sum)
    spectral_rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    spectral_bandwidth = float(
        np.sqrt(np.sum(((freqs - spectral_centroid) ** 2) * psd) / psd_sum)
    )

    # Frame-level energy variance
    frame_size = max(len(samples) // 8, 1)
    frame_energies = [
        float(np.mean(samples[i: i + frame_size] ** 2))
        for i in range(0, len(samples) - frame_size + 1, frame_size)
    ]
    energy_variance = float(np.var(frame_energies)) if len(frame_energies) > 1 else 0.0

    # Sub-band energy ratios  (low <500 Hz, mid 500-3 kHz, high >3 kHz)
    low_mask  = freqs < 500
    mid_mask  = (freqs >= 500)  & (freqs < 3000)
    high_mask = freqs >= 3000
    low_band_ratio  = float(np.sum(psd[low_mask]))  / (psd_sum + 1e-9)
    mid_band_ratio  = float(np.sum(psd[mid_mask]))  / (psd_sum + 1e-9)
    high_band_ratio = float(np.sum(psd[high_mask])) / (psd_sum + 1e-9)

    # Harmonic ratio — ratio of peak energy to mean (higher → more tonal / musical)
    harmonic_ratio = float(np.max(psd) / (np.mean(psd) + 1e-9))

    # Attack rate — how fast energy rises at the start (high → click / cough / clap)
    quarter = max(len(frame_energies) // 4, 1)
    early_energy = float(np.mean(frame_energies[:quarter])) if frame_energies else 0.0
    late_energy  = float(np.mean(frame_energies))           if frame_energies else 1e-9
    attack_rate  = early_energy / (late_energy + 1e-9)

    return {
        "rms_energy": rms_energy,
        "zcr": zcr,
        "spectral_centroid": spectral_centroid,
        "spectral_rolloff": spectral_rolloff,
        "spectral_bandwidth": spectral_bandwidth,
        "energy_variance": energy_variance,
        "low_band_ratio": low_band_ratio,
        "mid_band_ratio": mid_band_ratio,
        "high_band_ratio": high_band_ratio,
        "harmonic_ratio": harmonic_ratio,
        "attack_rate": attack_rate,
        "is_empty": False,
    }


def _descriptor_to_features(descriptor: dict, loudness_db: float) -> dict:
    """
    Normalize a segregation descriptor into the same feature dict shape
    so the rule engine works uniformly on both inputs.
    Missing keys fall back to 0.0.
    """
    return {
        "rms_energy":        descriptor.get("energy_ratio", 0.0),   # best proxy available
        "zcr":               descriptor.get("zcr", 0.0),
        "spectral_centroid": descriptor.get("spectral_centroid", 0.0),
        "spectral_rolloff":  descriptor.get("spectral_rolloff", 0.0),
        "spectral_bandwidth":descriptor.get("spectral_bandwidth", 0.0),
        "energy_variance":   descriptor.get("temporal_variance", 0.0),
        "low_band_ratio":    descriptor.get("low_band_ratio", 0.0),
        "mid_band_ratio":    descriptor.get("mid_band_ratio", 0.0),
        "high_band_ratio":   descriptor.get("high_band_ratio", 0.0),
        "harmonic_ratio":    descriptor.get("harmonic_ratio", 0.0),
        "attack_rate":       descriptor.get("attack_rate", 0.0),
        "is_empty":          descriptor.get("energy_ratio", 1.0) < 0.04,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rule engine  (returns a list of (label, confidence) tuples)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_rules(f: dict, loudness_db: float) -> list[tuple[str, float]]:
    """
    Multi-label rule engine.  A single audio component can match multiple
    labels if its features satisfy more than one rule (e.g., speech + cough).

    Each rule appends (label, confidence) independently.
    """
    labels: list[tuple[str, float]] = []

    rms       = f["rms_energy"]
    zcr       = f["zcr"]
    centroid  = f["spectral_centroid"]
    rolloff   = f["spectral_rolloff"]
    bw        = f["spectral_bandwidth"]
    e_var     = f["energy_variance"]
    low_r     = f["low_band_ratio"]
    high_r    = f["high_band_ratio"]
    harm_r    = f["harmonic_ratio"]
    attack    = f["attack_rate"]

    # ── Silence ──────────────────────────────────────────────────────────────
    if rms < 0.003 or loudness_db < -55 or f["is_empty"]:
        return [("silence", 0.92)]

    # ── Fan (mechanical steady hum) ──────────────────────────────────────────
    if (centroid < 500 and zcr < 0.05
            and e_var < 0.00005 and 0.005 < rms < 0.08):
        labels.append(("fan", 0.82))

    # ── AC (similar to fan but slightly wider bandwidth / higher centroid) ───
    if (500 <= centroid < 900 and zcr < 0.07
            and e_var < 0.0001 and 0.005 < rms < 0.12 and bw < 600):
        labels.append(("ac", 0.76))

    # ── Engine / motor (low-frequency rumble, moderate variance) ─────────────
    if (centroid < 700 and low_r > 0.5 and rms > 0.02 and e_var > 0.0001):
        labels.append(("engine", 0.74))

    # ── Traffic (broadband low-mid noise, louder) ─────────────────────────────
    if (200 < centroid < 1500 and rolloff > 800
            and bw > 400 and rms > 0.02):
        labels.append(("traffic", 0.74))

    # ── Rain (high-freq broadband hiss, very steady) ─────────────────────────
    if (centroid > 2000 and high_r > 0.35 and e_var < 0.0003
            and zcr > 0.15 and rms > 0.005):
        labels.append(("rain", 0.70))

    # ── Wind / breeze (low-mid broadband, very steady, low centroid) ─────────
    if (500 < centroid < 1800 and bw > 500 and e_var < 0.0002
            and zcr < 0.12 and rms > 0.008):
        labels.append(("wind", 0.68))

    # ── Thunder (sudden low-freq burst, high attack, high energy) ────────────
    if (centroid < 400 and low_r > 0.6 and attack > 2.0 and rms > 0.05):
        labels.append(("thunder", 0.72))

    # ── Speech ───────────────────────────────────────────────────────────────
    if (0.01 <= zcr <= 0.40 and 200 < centroid < 5000
            and rms > 0.003 and loudness_db > -55):
        conf = round(min(0.93, 0.65 + rms * 3.0), 2)
        labels.append(("speech", conf))

    # ── Cough (short broadband burst, fast attack, mid-high centroid) ────────
    if (centroid > 1000 and attack > 2.5 and bw > 600 and rms > 0.03
            and e_var > 0.001):
        labels.append(("cough", 0.71))

    # ── Sneeze (similar to cough but higher freq content) ────────────────────
    if (centroid > 2000 and high_r > 0.30 and attack > 3.0
            and rms > 0.04 and e_var > 0.002):
        labels.append(("sneeze", 0.68))

    # ── Clap / footstep (very high attack, broadband, transient) ─────────────
    if (attack > 4.0 and bw > 800 and rms > 0.04 and e_var > 0.003):
        labels.append(("clap", 0.65))

    # ── Keyboard clicks (high ZCR, high centroid, bursty variance) ───────────
    if (zcr > 0.30 and centroid > 2500 and e_var > 0.0005):
        labels.append(("keyboard", 0.72))

    # ── Music (tonal, mid centroid, moderate ZCR, high harmonic ratio) ───────
    if (500 < centroid < 3500 and bw > 700 and 0.05 < zcr < 0.25
            and rms > 0.015 and harm_r > 8):
        labels.append(("music", 0.68))

    # ── Singing (music-like but higher centroid + ZCR from voice formants) ───
    if (1000 < centroid < 4000 and harm_r > 10 and 0.10 < zcr < 0.35
            and rms > 0.015):
        labels.append(("singing", 0.65))

    # ── Bird song (high centroid, tonal, low rms) ─────────────────────────────
    if (centroid > 3000 and harm_r > 12 and zcr < 0.25
            and 0.005 < rms < 0.06):
        labels.append(("bird_song", 0.67))

    # ── Dog bark (low-mid burst, high energy variance, fast attack) ───────────
    if (300 < centroid < 1200 and attack > 1.8 and e_var > 0.002
            and rms > 0.03):
        labels.append(("dog_bark", 0.70))

    # ── Fallback ─────────────────────────────────────────────────────────────
    if not labels and rms > 0.005:
        labels.append(("background_noise", 0.50))
    elif not labels:
        labels.append(("silence", 0.60))

    return labels


# ─────────────────────────────────────────────────────────────────────────────
# Public API  (same function name as original)
# ─────────────────────────────────────────────────────────────────────────────

def classify_sound(
    pcm_bytes: bytes,
    loudness_db: float,
    descriptor: dict | None = None,
) -> dict:
    """
    Classify audio into one or more sound labels and broad categories.

    Args:
        pcm_bytes   : raw 16-bit mono PCM audio.
        loudness_db : loudness of the chunk in dBFS.
        descriptor  : optional pre-built feature dict from segregate_sounds()
                      component["descriptor"].  When provided, pcm_bytes is
                      used only to compute missing features (zcr, attack_rate).
                      Pass None to run full feature extraction from pcm_bytes.

    Returns:
        {
            "labels": [
                {
                    "sound_label"    : str,   # e.g. "speech", "fan", "rain"
                    "sound_category" : str,   # e.g. "human_activity", "natural"
                    "confidence"     : float,
                },
                ...
            ],
            # Convenience — dominant (highest confidence) label kept for
            # backward compatibility with callers expecting a flat response.
            "sound_type"    : str,
            "sound_subtype" : str | None,
            "confidence"    : float,
        }
    """
    # ── Feature extraction ───────────────────────────────────────────────────
    if descriptor is not None:
        features = _descriptor_to_features(descriptor, loudness_db)
        # Supplement with PCM-derived features if audio is available
        if pcm_bytes:
            pcm_features = _compute_features(pcm_bytes, loudness_db)
            for key in ("zcr", "attack_rate", "energy_variance", "harmonic_ratio"):
                if features.get(key, 0.0) == 0.0:
                    features[key] = pcm_features.get(key, 0.0)
    else:
        features = _compute_features(pcm_bytes, loudness_db)

    # ── Apply rules ──────────────────────────────────────────────────────────
    raw_labels = _apply_rules(features, loudness_db)

    # De-duplicate (keep highest confidence per label)
    seen: dict[str, float] = {}
    for label, conf in raw_labels:
        if label not in seen or conf > seen[label]:
            seen[label] = conf

    # Sort by confidence descending
    sorted_labels = sorted(seen.items(), key=lambda x: x[1], reverse=True)

    label_list = [
        {
            "sound_label":    lbl,
            "sound_category": CATEGORY_MAP.get(lbl, "unknown"),
            "confidence":     round(conf, 2),
        }
        for lbl, conf in sorted_labels
    ]

    # ── Dominant label (backward-compatible flat fields) ─────────────────────
    dominant = label_list[0] if label_list else {
        "sound_label": "silence", "sound_category": "silence", "confidence": 0.60
    }

    # Map dominant label → sound_type / sound_subtype (matches original schema)
    SUBTYPE_LABELS = {"fan", "ac", "engine", "traffic", "keyboard",
                      "rain", "wind", "thunder", "cough", "sneeze",
                      "clap", "dog_bark", "bird_song", "cat", "footsteps",
                      "background_noise", "singing"}
    TYPE_LABELS    = {"speech", "music", "silence"}

    dom_label = dominant["sound_label"]
    if dom_label in TYPE_LABELS:
        sound_type    = dom_label
        sound_subtype = None
    elif dom_label in SUBTYPE_LABELS:
        sound_type    = dominant["sound_category"] if dominant["sound_category"] != "silence" else "noise"
        sound_subtype = dom_label
    else:
        sound_type    = "noise"
        sound_subtype = dom_label

    result = {
        "labels":        label_list,
        "sound_type":    sound_type,
        "sound_subtype": sound_subtype,
        "confidence":    dominant["confidence"],
    }

    logger.debug(
        "classify_sound: dominant=%s | labels=%s",
        dom_label,
        [l["sound_label"] for l in label_list],
    )
    return result