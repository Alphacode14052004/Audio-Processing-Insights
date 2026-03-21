def estimate_distance(loudness_db: float, sound_type: str) -> dict:
    _ = sound_type
    if loudness_db > -15:
        return {"distance_label": "near", "distance_confidence": 0.85}
    if loudness_db > -30:
        return {"distance_label": "mid", "distance_confidence": 0.70}
    return {"distance_label": "far", "distance_confidence": 0.60}
