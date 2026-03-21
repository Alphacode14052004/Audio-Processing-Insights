Build a FastAPI backend for a real-time audio processing pipeline. This is the 
backend only — no frontend integration yet. All external AI service calls should 
be stubbed with mock responses so the pipeline runs end to end without real API keys.

--- PROJECT CONTEXT ---
A React Native app streams live audio chunks over WebSocket to this backend.
The backend processes the audio and streams back structured insights in real time.
One recording session = one WebSocket connection = one .wav file saved at the end.

--- TECH STACK ---
- Python 3.11+
- FastAPI + uvicorn
- WebSockets (built into FastAPI)
- SQLAlchemy (async) + aiosqlite for SQLite
- pydub for audio chunk assembly and WAV writing
- numpy for basic audio analysis (loudness calculation)
- python-dotenv for environment variables
- No Celery, no Redis — keep it simple and synchronous within each session

--- FOLDER STRUCTURE ---
backend/
  main.py                        — FastAPI app, mounts all routers
  database.py                    — SQLAlchemy engine, session factory, Base
  models.py                      — all ORM models (Session, Insight, Speaker)
  schemas.py                     — all Pydantic schemas for request/response
  routers/
    sessions.py                  — REST endpoints for session management
    websocket.py                 — WebSocket endpoint for live audio streaming
  services/
    audio_assembler.py           — buffers chunks, assembles final WAV file
    pipeline.py                  — orchestrates all processing steps per chunk
    diarization.py               — speaker diarization (stubbed)
    transcription.py             — speech to text (stubbed)
    sound_classifier.py          — sound type classification (stubbed)
    distance_estimator.py        — distance estimation from audio features
    loudness_analyzer.py         — loudness calculation using RMS (real implementation)
  storage/
    file_manager.py              — handles saving WAV files to disk
  utils/
    audio_utils.py               — base64 decode, PCM conversion helpers
    logger.py                    — structured logging setup
  recordings/                    — saved .wav files go here (gitignored)
  .env                           — environment variables
  requirements.txt

--- DATABASE MODELS (models.py) ---

RecordingSession:
  id: UUID (PK, auto-generated)
  device_id: String (which device sent this)
  started_at: DateTime
  ended_at: DateTime (nullable, set on stop)
  duration_seconds: Float (nullable)
  file_path: String (nullable, set after WAV is written)
  file_size_bytes: Integer (nullable)
  sample_rate: Integer (default 16000)
  channels: Integer (default 1)
  status: Enum('recording', 'processing', 'done', 'failed')
  total_insights: Integer (default 0)
  created_at: DateTime (auto)

Insight:
  id: UUID (PK, auto-generated)
  session_id: UUID (FK → RecordingSession.id)
  timestamp_ms: Integer (ms from session start when this insight was generated)
  speaker_label: String (nullable, e.g. "Speaker 1")
  speaker_confidence: Float (0.0-1.0, nullable)
  sound_type: String (e.g. "speech", "music", "noise", "silence")
  sound_subtype: String (nullable, e.g. "traffic", "keyboard", "laughter")
  transcript: Text (nullable, the spoken words)
  transcript_confidence: Float (nullable)
  loudness_db: Float (RMS dB value)
  loudness_label: String (e.g. "quiet", "moderate", "loud", "very_loud")
  distance_label: String (e.g. "near", "mid", "far")
  distance_confidence: Float
  raw_audio_features: JSON (store the numpy-computed features for debugging)
  created_at: DateTime (auto)

Speaker:
  id: UUID (PK, auto-generated)
  session_id: UUID (FK → RecordingSession.id)
  speaker_label: String (e.g. "Speaker 1")
  total_speaking_ms: Integer
  word_count: Integer
  avg_loudness_db: Float
  min_loudness_db: Float
  max_loudness_db: Float
  dominant_sound_type: String
  turn_count: Integer (how many separate speaking turns)
  first_heard_at_ms: Integer
  last_heard_at_ms: Integer
  created_at: DateTime (auto)

--- REST ENDPOINTS (routers/sessions.py) ---

POST /sessions/start
  Body: { device_id: string }
  Action: creates RecordingSession row with status='recording'
  Returns: { session_id: uuid, started_at: datetime, message: "Session started" }

POST /sessions/{session_id}/stop
  Action: 
    - updates session: ended_at, status='processing'
    - triggers WAV file write from assembled buffer
    - triggers speaker aggregation from insight rows
    - updates session: file_path, file_size_bytes, duration_seconds, 
      total_insights, status='done'
  Returns: { session_id, duration_seconds, total_insights, file_path, speakers: [...] }

GET /sessions/{session_id}
  Returns: full session object with nested insights and speakers

GET /sessions/{session_id}/insights
  Query params: limit (default 50), offset (default 0)
  Returns: paginated list of insight rows for that session

GET /sessions/{session_id}/speakers
  Returns: all speaker rows for that session

GET /sessions/
  Returns: list of all sessions (id, device_id, started_at, status, total_insights)

DELETE /sessions/{session_id}
  Deletes session row, all insight rows, all speaker rows, and the WAV file from disk

--- WEBSOCKET ENDPOINT (routers/websocket.py) ---

WS /ws/{session_id}
  
  Connection lifecycle:
  1. On connect: validate session_id exists and status='recording', 
     initialize AudioAssembler for this session
  2. On message (binary): audio chunk as base64-encoded string or raw bytes
  3. On message (text/JSON): handle control messages
     { type: "stop" } → trigger stop processing
     { type: "ping" } → respond with { type: "pong" }
  4. On disconnect: clean up assembler

  Per chunk processing (call pipeline.py):
  a. Decode base64 → raw PCM bytes
  b. Append to AudioAssembler buffer
  c. Run pipeline on this chunk:
     - compute loudness (real: RMS calculation)
     - classify sound type (stubbed)
     - run diarization (stubbed)
     - run transcription (stubbed)  
     - estimate distance (stubbed based on loudness)
  d. Insert Insight row to database
  e. Send insight back to client as JSON immediately

  Message sent back to client per chunk:
  {
    type: "insight",
    data: {
      insight_id: uuid,
      timestamp_ms: int,
      speaker_label: "Speaker 1" or null,
      sound_type: "speech",
      sound_subtype: null,
      transcript: "hello world" or null,
      loudness_db: -18.5,
      loudness_label: "moderate",
      distance_label: "near",
      distance_confidence: 0.75
    }
  }

  On stop signal:
  {
    type: "session_complete",
    data: {
      session_id: uuid,
      duration_seconds: float,
      total_insights: int,
      file_path: string,
      speakers: [ speaker objects ]
    }
  }

--- SERVICE IMPLEMENTATIONS ---

loudness_analyzer.py (REAL implementation using numpy):
  - Input: raw PCM bytes (16-bit, mono, 16000Hz)
  - Convert bytes → numpy int16 array → normalize to float32
  - Compute RMS → convert to dB: 20 * log10(rms + epsilon)
  - Map dB to label:
      > -10 dB  → "very_loud"
      > -20 dB  → "loud"
      > -35 dB  → "moderate"
      > -50 dB  → "quiet"
      else      → "silence"
  - Return: { loudness_db: float, loudness_label: string }

distance_estimator.py (REAL implementation, heuristic-based):
  - Input: loudness_db, sound_type
  - Heuristic rules:
      loudness > -15 dB  → near (confidence 0.85)
      loudness > -30 dB  → mid  (confidence 0.70)
      else               → far  (confidence 0.60)
  - Return: { distance_label: string, distance_confidence: float }

audio_assembler.py (REAL implementation):
  - Maintains a list of raw PCM byte chunks per session in memory
  - append_chunk(session_id, pcm_bytes): adds to buffer
  - get_buffer(session_id): returns concatenated bytes
  - write_wav(session_id, output_path): writes proper WAV file using pydub
    - sets frame_rate=16000, sample_width=2, channels=1
  - clear(session_id): frees memory after file is written
  - get_duration_ms(session_id): computes duration from buffer size

diarization.py (STUBBED — clearly marked for future replacement):
  - Simulate 2-3 speakers rotating per chunk
  - Return consistent speaker labels within a session 
    (don't randomly assign — use a simple round-robin every 10 chunks
     so the output looks realistic)
  - Return: { speaker_label: "Speaker 1", confidence: 0.82 }
  - Add a comment: # TODO: replace with pyannote.audio integration

transcription.py (STUBBED — clearly marked for future replacement):
  - Return a rotating set of 5-6 realistic placeholder sentences
    (e.g. "This is a test recording.", "The audio pipeline is working.", etc.)
  - Only return transcript if sound_type is "speech", else return None
  - Return: { transcript: string or None, confidence: float }
  - Add a comment: # TODO: replace with Deepgram/Whisper API call

sound_classifier.py (STUBBED — clearly marked for future replacement):
  - Use loudness_db to make a semi-realistic guess:
      loudness > -25 and has_speech_pattern → "speech"
      loudness > -30 → "ambient"
      else → "silence"
  - Randomly assign subtype from ["background_noise", "keyboard", "traffic", None]
    with weighted probability (None most common)
  - Return: { sound_type: string, sound_subtype: string or None, confidence: float }
  - Add a comment: # TODO: replace with YAMNet or similar audio classifier

pipeline.py (orchestrator):
  - Takes raw PCM bytes + session context
  - Calls all services in order:
    1. loudness_analyzer → always runs first (needed by distance_estimator)
    2. sound_classifier  → uses loudness as input
    3. distance_estimator → uses loudness + sound_type
    4. diarization       → uses sound_type (skip if not speech)
    5. transcription     → uses sound_type (skip if not speech)
  - Assembles InsightCreate schema from all results
  - Returns the assembled insight dict
  - Log processing time for each step

--- SPEAKER AGGREGATION ---

In sessions.py, after stop is called, run aggregation:
- Query all Insight rows for this session_id
- Group by speaker_label
- For each speaker compute:
    total_speaking_ms: count insights × chunk_duration_ms
    word_count: sum of word counts from transcripts
    avg/min/max loudness_db: from insight rows
    dominant_sound_type: most common sound_type
    turn_count: count consecutive insight groups per speaker
    first_heard_at_ms / last_heard_at_ms: from timestamp_ms
- Insert Speaker rows for each unique speaker found

--- AUDIO UTILS (utils/audio_utils.py) ---
- decode_base64_audio(b64_string) → bytes
- pcm_bytes_to_numpy(pcm_bytes) → np.ndarray (float32, normalized -1 to 1)
- strip_wav_header(wav_bytes) → raw PCM bytes
  (WAV header is 44 bytes — strip it from first chunk of each session)
- compute_chunk_duration_ms(pcm_bytes, sample_rate=16000) → float

--- ENVIRONMENT VARIABLES (.env) ---
DATABASE_URL=sqlite+aiosqlite:///./momOS.db
RECORDINGS_DIR=./recordings
MAX_RECORDING_DURATION_SECONDS=3600
CHUNK_DURATION_MS=250
LOG_LEVEL=INFO
# Future keys (not used yet, just define them)
DEEPGRAM_API_KEY=
OPENAI_API_KEY=
PYANNOTE_AUTH_TOKEN=

--- ERROR HANDLING ---
- All WebSocket message handlers wrapped in try/except
- If processing a chunk fails, send error message to client but keep connection open:
  { type: "error", message: "chunk processing failed", fatal: false }
- If session not found on WS connect, close with code 4004
- All DB operations use async context managers
- Log all errors with session_id context

--- TESTING THE PIPELINE ---
Create a test script test_pipeline.py in the root that:
- Creates a session via POST /sessions/start
- Simulates sending 20 audio chunks (use numpy to generate random PCM bytes)
- Calls POST /sessions/{id}/stop
- Prints the full session summary
This should run with: python test_pipeline.py and show the full pipeline working

--- STARTUP AND DOCS ---
- Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
- Auto-docs available at: http://localhost:8000/docs
- Add a GET / health check: returns { status: "ok", version: "1.0.0" }
- On startup: create recordings/ directory if not exists, run DB migrations

--- CONSTRAINTS ---
- All async (use async def everywhere, AsyncSession for DB)
- No authentication for now (add TODO comments where auth would go)
- All stubs must be clearly marked with # STUB and # TODO comments
- requirements.txt must be complete and pinned to specific versions
- The pipeline must process one chunk in under 100ms (stubs make this easy)
- Every service must be independently importable and testable