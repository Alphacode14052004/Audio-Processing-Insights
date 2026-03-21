import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class SessionStatus(str, enum.Enum):
    recording = "recording"
    processing = "processing"
    done = "done"
    failed = "failed"


class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=16000)
    channels: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, native_enum=False), nullable=False, default=SessionStatus.recording, index=True
    )
    total_insights: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    insights: Mapped[list["Insight"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    speakers: Mapped[list["Speaker"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recording_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    speaker_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    speaker_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sound_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sound_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loudness_db: Mapped[float] = mapped_column(Float, nullable=False)
    audio_intensity_rms: Mapped[float | None] = mapped_column(Float, nullable=True)
    loudness_label: Mapped[str] = mapped_column(String(30), nullable=False)
    distance_label: Mapped[str] = mapped_column(String(30), nullable=False)
    distance_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    raw_audio_features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped[RecordingSession] = relationship(back_populates="insights")


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recording_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    total_speaking_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_loudness_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_loudness_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_loudness_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dominant_sound_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_heard_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_heard_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped[RecordingSession] = relationship(back_populates="speakers")
