"""
Sound Segregation — Milestone 4
Separates a mixed audio chunk into distinct background sound components
using STFT + Non-negative Matrix Factorization (NMF).

No model downloads required — uses only numpy + scipy.

Output: a list of isolated component waveforms (as PCM bytes) plus
        a brief descriptor for each component so the classifier can
        label them independently.
"""

import numpy as np
from scipy import signal as scipy_signal
from scipy.signal import istft

from utils.logger import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16000

# ── STFT parameters ──────────────────────────────────────────────────────────
N_FFT = 512          # FFT window size (~32 ms at 16 kHz)
HOP_LENGTH = 128     # overlap (~8 ms hop)
N_COMPONENTS = 4     # NMF rank — max distinct sources we try to separate


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_mono_float(pcm_bytes: bytes) -> np.ndarray:
    """Convert raw 16-bit PCM bytes → normalized float32 mono array."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size == 0:
        return np.array([], dtype=np.float32)
    return samples.astype(np.float32) / 32768.0


def _float_to_pcm(samples: np.ndarray) -> bytes:
    """Convert float32 array back to raw 16-bit PCM bytes."""
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


def _stft(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute the Short-Time Fourier Transform.

    Returns:
        freqs   : frequency bins  (F,)
        times   : time frames     (T,)
        Z       : complex STFT    (F, T)
    """
    freqs, times, Z = scipy_signal.stft(
        samples,
        fs=SAMPLE_RATE,
        window="hann",
        nperseg=N_FFT,
        noverlap=N_FFT - HOP_LENGTH,
    )
    return freqs, times, Z


def _nmf(V: np.ndarray, n_components: int, max_iter: int = 300) -> tuple[np.ndarray, np.ndarray]:
    """
    Multiplicative-update NMF:  V ≈ W · H
    V : (F, T)  non-negative magnitude spectrogram
    W : (F, K)  basis spectra  (one per component)
    H : (K, T)  activations    (energy of each component over time)
    """
    F, T = V.shape
    rng = np.random.default_rng(seed=0)
    W = rng.uniform(0.01, 1.0, (F, n_components)).astype(np.float32)
    H = rng.uniform(0.01, 1.0, (n_components, T)).astype(np.float32)
    eps = 1e-9

    for _ in range(max_iter):
        # Update H
        WtV = W.T @ V
        WtWH = (W.T @ W) @ H + eps
        H *= WtV / WtWH

        # Update W
        VHt = V @ H.T
        WHHt = W @ (H @ H.T) + eps
        W *= VHt / WHHt

    return W, H


def _component_descriptor(W_col: np.ndarray, H_row: np.ndarray, freqs: np.ndarray) -> dict:
    """
    Derive lightweight spectral descriptors for one NMF component so the
    downstream classifier can work with it without re-running feature extraction.
    """
    psd_sum = float(np.sum(W_col)) + 1e-9
    centroid = float(np.sum(freqs * W_col) / psd_sum)

    cumsum = np.cumsum(W_col)
    rolloff_idx = np.searchsorted(cumsum, 0.85 * cumsum[-1])
    rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * W_col) / psd_sum))
    energy_ratio = float(np.sum(H_row) / (np.sum(H_row) + 1e-9))  # relative contribution
    temporal_variance = float(np.var(H_row))

    return {
        "spectral_centroid": centroid,
        "spectral_rolloff": rolloff,
        "spectral_bandwidth": bandwidth,
        "temporal_variance": temporal_variance,
        "energy_ratio": energy_ratio,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def segregate_sounds(pcm_bytes: bytes, loudness_db: float) -> list[dict]:
    """
    Segregate a mixed audio chunk into distinct sound components.

    Args:
        pcm_bytes   : raw 16-bit mono PCM audio
        loudness_db : loudness of the chunk in dBFS (from VAD / meter)

    Returns:
        List of component dicts, each containing:
        {
            "component_id"  : int,           # 0-indexed
            "pcm_bytes"     : bytes,         # isolated waveform (same length as input)
            "energy_ratio"  : float,         # fraction of total energy this component holds
            "descriptor"    : dict,          # spectral features for downstream classifier
        }

        Returns an empty list if the audio is silent or too short.
    """
    samples = _to_mono_float(pcm_bytes)

    # ── Guard: silence / too short ───────────────────────────────────────────
    if samples.size < N_FFT:
        logger.debug("segregate_sounds: chunk too short (%d samples), skipping", samples.size)
        return []

    rms = float(np.sqrt(np.mean(samples ** 2)))
    if rms < 0.002 or loudness_db < -60:
        logger.debug("segregate_sounds: silent chunk (rms=%.4f, db=%.1f)", rms, loudness_db)
        return []

    # ── STFT ─────────────────────────────────────────────────────────────────
    freqs, times, Z = _stft(samples)
    magnitude = np.abs(Z).astype(np.float32)          # (F, T)
    phase = np.angle(Z)                                # (F, T) — kept for reconstruction

    # ── Adaptive component count ──────────────────────────────────────────────
    # Use fewer components for short / quiet chunks to stay stable
    n_comp = min(N_COMPONENTS, max(2, magnitude.shape[1] // 8))

    # ── NMF decomposition ────────────────────────────────────────────────────
    W, H = _nmf(magnitude, n_components=n_comp)       # W:(F,K), H:(K,T)

    # ── Reconstruct each component's waveform via masked STFT ────────────────
    components = []
    total_energy = float(np.sum(magnitude)) + 1e-9

    for k in range(n_comp):
        # Soft Wiener-style mask for component k
        component_mag = np.outer(W[:, k], H[k, :])    # (F, T)
        # Full reconstruction = W @ H  (equivalent to summing all outer products)
        reconstruction = W @ H                         # (F, T)
        mask = component_mag / (reconstruction + 1e-9) # (F, T)

        # Apply mask in complex domain and invert STFT
        Z_masked = mask * magnitude * np.exp(1j * phase)
        _, waveform = istft(
            Z_masked,
            fs=SAMPLE_RATE,
            window="hann",
            nperseg=N_FFT,
            noverlap=N_FFT - HOP_LENGTH,
        )

        # Trim / pad to match original length
        target_len = len(samples)
        if len(waveform) > target_len:
            waveform = waveform[:target_len]
        elif len(waveform) < target_len:
            waveform = np.pad(waveform, (0, target_len - len(waveform)))

        comp_energy = float(np.sum(component_mag))
        energy_ratio = comp_energy / total_energy

        # Skip near-zero components (NMF noise floor)
        if energy_ratio < 0.04:
            logger.debug("segregate_sounds: component %d negligible (ratio=%.3f), dropped", k, energy_ratio)
            continue

        descriptor = _component_descriptor(W[:, k], H[k, :], freqs)
        descriptor["energy_ratio"] = energy_ratio

        components.append(
            {
                "component_id": k,
                "pcm_bytes": _float_to_pcm(waveform.astype(np.float32)),
                "energy_ratio": energy_ratio,
                "descriptor": descriptor,
            }
        )
        logger.debug(
            "segregate_sounds: component %d | energy_ratio=%.3f | centroid=%.0f Hz",
            k,
            energy_ratio,
            descriptor["spectral_centroid"],
        )

    # Sort strongest component first
    components.sort(key=lambda c: c["energy_ratio"], reverse=True)
    return components