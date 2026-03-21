from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionStartRequest(BaseModel):
    device_id: str


class SessionStartResponse(BaseModel):
    session_id: str
    started_at: datetime
    message: str


class InsightBase(BaseModel):
    timestamp_ms: int
    speaker_label: str | None = None
    speaker_confidence: float | None = None
    sound_type: str
    sound_subtype: str | None = None
    transcript: str | None = None
    transcript_confidence: float | None = None
    speaker_count: int = 0
    loudness_db: float
    audio_intensity_rms: float | None = None
    loudness_label: str
    distance_label: str
    distance_confidence: float
    raw_audio_features: dict


class InsightCreate(InsightBase):
    session_id: str


class InsightResponse(InsightBase):
    id: str
    session_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpeakerResponse(BaseModel):
    id: str
    session_id: str
    speaker_label: str
    total_speaking_ms: int
    word_count: int
    avg_loudness_db: float
    min_loudness_db: float
    max_loudness_db: float
    dominant_sound_type: str
    turn_count: int
    first_heard_at_ms: int
    last_heard_at_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionListItem(BaseModel):
    id: str
    device_id: str
    started_at: datetime
    status: str
    total_insights: int

    model_config = ConfigDict(from_attributes=True)


class RecordingSessionResponse(BaseModel):
    id: str
    device_id: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    sample_rate: int
    channels: int
    status: str
    total_insights: int
    created_at: datetime
    insights: list[InsightResponse] = []
    speakers: list[SpeakerResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SessionStopResponse(BaseModel):
    session_id: str
    duration_seconds: float
    total_insights: int
    file_path: str
    speakers: list[SpeakerResponse]
