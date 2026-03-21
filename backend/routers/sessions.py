import os
from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Insight, RecordingSession, SessionStatus, Speaker
from schemas import (
    InsightResponse,
    RecordingSessionResponse,
    SessionListItem,
    SessionStartRequest,
    SessionStartResponse,
    SessionStopResponse,
    SpeakerResponse,
)
from services.audio_assembler import audio_assembler
from services.diarization import clear_session_buffer as clear_diarization_buffer
from storage.file_manager import delete_file_if_exists, generate_recording_path
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

CHUNK_DURATION_MS = int(os.getenv("CHUNK_DURATION_MS", "250"))
RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", "./recordings")


async def _aggregate_speakers(db: AsyncSession, session_id: str) -> list[Speaker]:
    result = await db.execute(
        select(Insight).where(Insight.session_id == session_id).order_by(Insight.timestamp_ms.asc())
    )
    insights = result.scalars().all()
    if not insights:
        return []

    grouped: dict[str, list[Insight]] = defaultdict(list)
    for insight in insights:
        if insight.speaker_label:
            grouped[insight.speaker_label].append(insight)

    if not grouped:
        return []

    await db.execute(delete(Speaker).where(Speaker.session_id == session_id))

    turn_counter: Counter[str] = Counter()
    prev_speaker = None
    for insight in insights:
        if not insight.speaker_label:
            prev_speaker = None
            continue
        if insight.speaker_label != prev_speaker:
            turn_counter[insight.speaker_label] += 1
            prev_speaker = insight.speaker_label

    speakers: list[Speaker] = []
    for speaker_label, speaker_insights in grouped.items():
        loudness_values = [item.loudness_db for item in speaker_insights]
        transcripts = [item.transcript for item in speaker_insights if item.transcript]
        words = sum(len(text.split()) for text in transcripts)
        sound_counter = Counter(item.sound_type for item in speaker_insights)
        dominant_sound_type = sound_counter.most_common(1)[0][0] if sound_counter else "unknown"

        speaker = Speaker(
            session_id=session_id,
            speaker_label=speaker_label,
            total_speaking_ms=len(speaker_insights) * CHUNK_DURATION_MS,
            word_count=words,
            avg_loudness_db=sum(loudness_values) / len(loudness_values),
            min_loudness_db=min(loudness_values),
            max_loudness_db=max(loudness_values),
            dominant_sound_type=dominant_sound_type,
            turn_count=turn_counter[speaker_label],
            first_heard_at_ms=min(item.timestamp_ms for item in speaker_insights),
            last_heard_at_ms=max(item.timestamp_ms for item in speaker_insights),
        )
        db.add(speaker)
        speakers.append(speaker)

    await db.flush()
    return speakers


async def finalize_session(
    db: AsyncSession,
    session: RecordingSession,
    force_time: datetime | None = None,
) -> SessionStopResponse:
    if session.status == SessionStatus.done:
        speaker_result = await db.execute(select(Speaker).where(Speaker.session_id == session.id))
        speakers = speaker_result.scalars().all()
        return SessionStopResponse(
            session_id=session.id,
            duration_seconds=session.duration_seconds or 0.0,
            total_insights=session.total_insights,
            file_path=session.file_path or "",
            speakers=[SpeakerResponse.model_validate(item) for item in speakers],
        )

    session.status = SessionStatus.processing
    session.ended_at = force_time or datetime.utcnow()
    await db.flush()

    output_path = generate_recording_path(RECORDINGS_DIR, session.id)
    audio_assembler.write_wav(session.id, output_path)
    duration_seconds = audio_assembler.get_duration_ms(session.id) / 1000.0
    audio_assembler.clear(session.id)
    clear_diarization_buffer(session.id)

    insights_count_result = await db.execute(
        select(func.count(Insight.id)).where(Insight.session_id == session.id)
    )
    total_insights = int(insights_count_result.scalar_one() or 0)

    speakers = await _aggregate_speakers(db, session.id)

    session.duration_seconds = duration_seconds
    session.file_path = output_path
    session.file_size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    session.total_insights = total_insights
    session.status = SessionStatus.done

    await db.commit()
    for speaker in speakers:
        await db.refresh(speaker)

    return SessionStopResponse(
        session_id=session.id,
        duration_seconds=duration_seconds,
        total_insights=total_insights,
        file_path=output_path,
        speakers=[SpeakerResponse.model_validate(item) for item in speakers],
    )


@router.post("/start", response_model=SessionStartResponse)
async def start_session(payload: SessionStartRequest, db: AsyncSession = Depends(get_db)):
    # TODO: Add authentication/authorization checks.
    session = RecordingSession(device_id=payload.device_id, status=SessionStatus.recording)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionStartResponse(session_id=session.id, started_at=session.started_at, message="Session started")


@router.post("/{session_id}/stop", response_model=SessionStopResponse)
async def stop_session(session_id: str, db: AsyncSession = Depends(get_db)):
    # TODO: Add authentication/authorization checks.
    session = await db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await finalize_session(db, session)


@router.get("/{session_id}", response_model=RecordingSessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RecordingSession)
        .where(RecordingSession.id == session_id)
        .options(selectinload(RecordingSession.insights), selectinload(RecordingSession.speakers))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return RecordingSessionResponse.model_validate(session)


@router.get("/{session_id}/insights", response_model=list[InsightResponse])
async def get_insights(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(Insight)
        .where(Insight.session_id == session_id)
        .order_by(Insight.timestamp_ms.asc())
        .limit(limit)
        .offset(offset)
    )
    return [InsightResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/{session_id}/speakers", response_model=list[SpeakerResponse])
async def get_speakers(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(select(Speaker).where(Speaker.session_id == session_id))
    return [SpeakerResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/", response_model=list[SessionListItem])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RecordingSession).order_by(RecordingSession.started_at.desc()))
    sessions = result.scalars().all()
    return [SessionListItem.model_validate(item) for item in sessions]


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    # TODO: Add authentication/authorization checks.
    session = await db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.file_path:
        delete_file_if_exists(session.file_path)

    await db.delete(session)
    await db.commit()
    logger.info("Session deleted", extra={"session_id": session_id})
    return {"deleted": True, "session_id": session_id}
