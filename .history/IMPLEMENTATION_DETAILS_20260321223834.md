# Real-Time Audio Intelligence Backend — Implementation Details

## 1) Project Goal

This backend receives live audio chunks over WebSocket, processes each chunk in near real-time, stores structured insights in SQLite, and finalizes one WAV recording per session.

One recording session maps to:
- one DB session row (`RecordingSession`)
- one WebSocket connection (`/ws/{session_id}`)
- one final WAV file in `backend/recordings/`

---

## 2) Current Folder Layout (Implemented)

- `backend/main.py` — FastAPI app bootstrap, startup lifecycle, health routes, router registration
- `backend/database.py` — async SQLAlchemy engine, session factory, `Base`, table init
- `backend/models.py` — ORM models: `RecordingSession`, `Insight`, `Speaker`
- `backend/schemas.py` — Pydantic request/response schemas
- `backend/routers/sessions.py` — REST session APIs + stop/finalize + speaker aggregation
- `backend/routers/websocket.py` — WebSocket stream handling and per-chunk processing
- `backend/services/audio_assembler.py` — in-memory chunk buffer + WAV writing
- `backend/services/pipeline.py` — orchestrates service calls per chunk and assembles insight payload
- `backend/services/loudness_analyzer.py` — real RMS/dB loudness implementation
- `backend/services/distance_estimator.py` — real heuristic distance estimation
- `backend/services/sound_classifier.py` — STUB classifier
- `backend/services/diarization.py` — STUB diarization
- `backend/services/transcription.py` — STUB transcription
- `backend/storage/file_manager.py` — file path creation and file deletion helpers
- `backend/utils/audio_utils.py` — base64 decode, WAV header strip, PCM utility helpers
- `backend/utils/logger.py` — logging setup helper
- `backend/.env` — environment config
- `backend/requirements.txt` — pinned dependencies
- `test_pipeline.py` — synthetic chunk E2E test
- `test_pipeline_wav.py` — WAV-file-based E2E test

---

## 3) Startup and App Lifecycle

`backend/main.py` does the following:

1. Loads environment variables (`python-dotenv`)
2. Configures logging
3. On startup (`lifespan`):
   - creates `RECORDINGS_DIR` if missing
   - runs DB table initialization (`Base.metadata.create_all`)
4. Registers endpoints:
   - `GET /`
   - `GET /health`
   - REST routes under `/sessions`
   - WebSocket route `/ws/{session_id}`

---

## 4) Data Model Design

### `RecordingSession`
Tracks session lifecycle and file metadata:
- `id`, `device_id`, `started_at`, `ended_at`
- `status`: `recording | processing | done | failed`
- `duration_seconds`, `file_path`, `file_size_bytes`
- `sample_rate`, `channels`, `total_insights`

### `Insight`
One row per processed chunk:
- temporal info: `timestamp_ms`
- classification info: `sound_type`, `sound_subtype`
- speech info: `speaker_label`, `speaker_confidence`, `transcript`, `transcript_confidence`
- acoustic info: `loudness_db`, `loudness_label`, `distance_label`, `distance_confidence`
- debug info: `raw_audio_features` (JSON)

### `Speaker`
Aggregated speaker stats computed at stop/finalize:
- `speaker_label`
- `total_speaking_ms`, `word_count`
- `avg/min/max loudness`
- `dominant_sound_type`
- `turn_count`
- `first_heard_at_ms`, `last_heard_at_ms`

---

## 5) REST API Implementation

### `POST /sessions/start`
- Input: `{ "device_id": "..." }`
- Creates `RecordingSession` with `status=recording`
- Returns `session_id`, `started_at`, message

### `POST /sessions/{session_id}/stop`
Finalizes a session:
1. marks status as `processing`
2. writes buffered PCM to WAV
3. computes duration, size, total insights
4. aggregates speakers from insights
5. marks session `done`
6. returns final summary + speakers

### `GET /sessions/{session_id}`
Returns full nested object:
- session fields
- `insights[]`
- `speakers[]`

### `GET /sessions/{session_id}/insights`
Paginated insights list (`limit`, `offset`)

### `GET /sessions/{session_id}/speakers`
Speaker aggregate list

### `GET /sessions/`
Session summary list

### `DELETE /sessions/{session_id}`
Deletes DB records and WAV file

---

## 6) WebSocket Processing Flow (`/ws/{session_id}`)

### Connect
- Validates session exists and is in `recording`
- Otherwise closes with code `4004`

### Per binary message (chunk)
1. Decode incoming bytes (raw bytes or base64 bytes)
2. Strip WAV header from first chunk if present
3. Append to `AudioAssembler` in-memory buffer
4. Run pipeline (`services/pipeline.py`)
5. Persist `Insight`
6. Send immediate insight JSON:
   - `insight_id`, `timestamp_ms`, `speaker_label`
   - `sound_type`, `sound_subtype`, `transcript`
   - `loudness_db`, `loudness_label`, `distance_label`, `distance_confidence`

### Text control messages
- `{ "type": "ping" }` -> `{ "type": "pong" }`
- `{ "type": "stop" }` -> finalize session and return `session_complete`

### Error handling
- Chunk errors return non-fatal WS error payload and keep socket open
- General WS failures are logged with `session_id`
- Assembler buffer is cleared in `finally`

---

## 7) Service-Level Implementations

## 7.1 Real: Loudness Analyzer
`backend/services/loudness_analyzer.py`
- PCM bytes -> `np.int16` -> normalized float
- Computes RMS
- Converts to dB using `20 * log10(rms + epsilon)`
- Maps dB to labels:
  - `> -10`: `very_loud`
  - `> -20`: `loud`
  - `> -35`: `moderate`
  - `> -50`: `quiet`
  - else: `silence`

## 7.2 Real: Distance Estimator
`backend/services/distance_estimator.py`
- Heuristic mapping from loudness:
  - `> -15`: `near` (0.85)
  - `> -30`: `mid` (0.70)
  - else: `far` (0.60)

## 7.3 Real: Audio Assembler
`backend/services/audio_assembler.py`
- Maintains chunk buffer per session
- Exposes:
  - `append_chunk`
  - `get_buffer`
  - `get_duration_ms`
  - `write_wav`
  - `clear`
- WAV writing uses `pydub.AudioSegment` with:
  - `frame_rate=16000`
  - `sample_width=2`
  - `channels=1`

## 7.4 STUB: Sound Classifier
`backend/services/sound_classifier.py`
- Marked as STUB/TODO
- Uses loudness + lightweight signal heuristic to emit:
  - `speech`, `ambient`, or `silence`
- Emits weighted random subtype (`None` most frequent)

## 7.5 STUB: Diarization
`backend/services/diarization.py`
- Marked as STUB/TODO
- Simulates 2–3 speakers by round-robin windows
- Keeps session-consistent labels

## 7.6 STUB: Transcription
`backend/services/transcription.py`
- Marked as STUB/TODO
- Emits rotating realistic placeholder sentences
- Only returns transcript for `speech` chunks

## 7.7 Orchestrator: Pipeline
`backend/services/pipeline.py`
Execution order per chunk:
1. loudness
2. sound classification
3. distance estimation
4. diarization (if speech)
5. transcription (if speech)

Also computes lightweight debug audio features and logs per-step timings.

---

## 8) Speaker Aggregation Logic

Implemented in `backend/routers/sessions.py` during stop/finalize:

1. Fetch all session insights ordered by `timestamp_ms`
2. Group by `speaker_label`
3. For each speaker compute:
   - speaking time (`count * CHUNK_DURATION_MS`)
   - word count (split transcript words)
   - avg/min/max loudness
   - dominant sound type (mode)
   - turn count (speaker switch groups)
   - first/last timestamps
4. Store rows in `Speaker` table

---

## 9) Testing Implemented

## 9.1 Synthetic E2E test
`test_pipeline.py`
- starts session
- sends random PCM chunks over WS
- sends stop
- prints final summary

## 9.2 WAV-driven E2E test
`test_pipeline_wav.py`
- reads a WAV file
- streams chunks over WS
- supports `--chunk-ms`, `--max-chunks`, `--stop-timeout`
- verifies `session_complete` and persisted session summary

---

## 10) Key Fixes Applied During Validation

1. Added `GET /health` endpoint alias (in addition to `/`) for standard health probes
2. Fixed WebSocket `session_complete` JSON serialization issue:
   - changed from `model_dump()` to `model_dump(mode="json")`
   - resolves `datetime is not JSON serializable`

---

## 11) Current Status

Implemented and verified:
- session lifecycle (start -> stream -> stop -> done)
- per-chunk real-time insight generation and storage
- WAV persistence to disk
- speaker aggregation and retrieval
- health checks and API docs

Still intentionally stubbed (future integrations):
- production diarization
- production transcription
- production sound classification
- authentication/authorization

---

## 12) Useful Run Commands

### Start backend
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run synthetic test
```bash
python test_pipeline.py
```

### Run WAV test
```bash
python test_pipeline_wav.py --wav backend/recordings/testingaudio.wav --chunk-ms 250 --max-chunks 40 --stop-timeout 45
```

---

## 13) Where to Inspect Outputs

- Swagger docs: `http://127.0.0.1:8000/docs`
- Full session: `GET /sessions/{session_id}`
- Insights: `GET /sessions/{session_id}/insights`
- Speakers: `GET /sessions/{session_id}/speakers`
- DB file: `backend/momOS.db`
- WAV outputs: `backend/recordings/`
