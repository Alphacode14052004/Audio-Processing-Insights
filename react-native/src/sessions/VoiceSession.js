import { Audio } from 'expo-av';
import { BASE_HTTP, BASE_WS } from '../api/config';

// How often (ms) to cut and send an audio chunk
const CHUNK_INTERVAL_MS = 500;

// ─── Field mapper ─────────────────────────────────────────────────────────────
// Maps backend snake_case fields to the UI's camelCase field names
const mapInsight = (data) => ({
  // Core identification
  speaker:      data.speaker_label || null,
  soundType:    data.sound_type    || 'unknown',
  speech:       data.transcript    || null,

  // Acoustic details
  loudness:     data.loudness_label || 'unknown',
  loudness_db:  data.loudness_db   != null ? data.loudness_db.toFixed(1) : null,
  distance:     data.distance_label || 'unknown',

  // Session metadata
  timestamp:    data.timestamp_ms  ?? Date.now(),
  speakerCount: data.speaker_count ?? 0,
  insightId:    data.insight_id    || null,

  // Multi-label sound output (new)
  soundLabels:  data.sound_labels  || [],
});

// ─── VoiceSession ─────────────────────────────────────────────────────────────
class VoiceSession {
  constructor() {
    this.dataCallback     = null;   // (insight) => void — called per chunk
    this.completeCallback = null;   // (session)  => void — called on session_complete

    this.isActive      = false;
    this.sessionId     = null;      // assigned by POST /sessions/start
    this.ws            = null;      // WebSocket connection
    this.recording     = null;      // current Audio.Recording
    this.chunkInterval = null;      // setInterval handle
  }

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  async start() {
    if (this.isActive) return;
    this.isActive = true;

    // 1. Microphone permission
    const { granted } = await Audio.requestPermissionsAsync();
    if (!granted) {
      console.warn('[VoiceSession] Microphone permission denied');
      this.isActive = false;
      return;
    }

    // 2. Configure audio mode
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });

    // 3. Create session on backend (POST /sessions/start)
    try {
      const res = await fetch(`${BASE_HTTP}/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: 'expo-go-android' }),
      });
      const session = await res.json();
      this.sessionId = session.session_id;
      console.log('[VoiceSession] Session created:', this.sessionId);
    } catch (e) {
      console.error('[VoiceSession] Failed to create session:', e.message);
      this.isActive = false;
      return;
    }

    // 4. Open WebSocket with session_id
    this._connectWebSocket();

    // 5. Start first audio chunk
    await this._startNewChunk();

    // 6. Rotate chunks every 500ms
    this.chunkInterval = setInterval(() => this._rotateChunk(), CHUNK_INTERVAL_MS);
  }

  stop() {
    this.isActive = false;

    clearInterval(this.chunkInterval);
    this.chunkInterval = null;

    if (this.recording) {
      this.recording.stopAndUnloadAsync().catch(() => {});
      this.recording = null;
    }

    // Send stop signal then close WebSocket
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try { this.ws.send(JSON.stringify({ type: 'stop' })); } catch (_) {}
    }
  }

  destroy() {
    this.stop();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.dataCallback     = null;
    this.completeCallback = null;
  }

  // ─── Public callbacks ─────────────────────────────────────────────────────

  /** Called with each mapped insight while recording */
  onData(callback) { this.dataCallback = callback; }

  /** Called once with the full session object after recording stops */
  onComplete(callback) { this.completeCallback = callback; }

  // ─── WebSocket ────────────────────────────────────────────────────────────

  _connectWebSocket() {
    const url = `${BASE_WS}/ws/${this.sessionId}`;
    console.log('[VoiceSession] Connecting WS:', url);
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[VoiceSession] WebSocket connected');
    };

    this.ws.onclose = () => {
      console.log('[VoiceSession] WebSocket disconnected');
    };

    this.ws.onerror = (e) => {
      console.warn('[VoiceSession] WebSocket error:', e.message || 'Connection failed');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'insight' && this.dataCallback) {
          // Live insight — map and push to UI
          this.dataCallback(mapInsight(msg.data));

        } else if (msg.type === 'session_complete') {
          // Session done — fetch full session then notify
          console.log('[VoiceSession] session_complete received, fetching full session…');
          this._fetchAndCompleteSession();

        } else if (msg.type === 'error') {
          console.warn('[VoiceSession] Backend error:', msg.message);
        }
      } catch (e) {
        console.warn('[VoiceSession] Failed to parse message:', e);
      }
    };
  }

  async _fetchAndCompleteSession() {
    if (!this.sessionId) return;

    // Close WS after session_complete
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    try {
      const res = await fetch(`${BASE_HTTP}/sessions/${this.sessionId}`);
      const session = await res.json();
      console.log('[VoiceSession] Full session loaded:', session.id, '—', session.total_insights, 'insights');

      if (this.completeCallback) {
        this.completeCallback(session);
      }
    } catch (e) {
      console.error('[VoiceSession] Failed to fetch session:', e.message);
    }
  }

  // ─── Audio Chunking ───────────────────────────────────────────────────────

  async _startNewChunk() {
    try {
      this.recording = new Audio.Recording();
      await this.recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await this.recording.startAsync();
    } catch (e) {
      console.warn('[VoiceSession] Failed to start audio chunk:', e);
    }
  }

  async _rotateChunk() {
    if (!this.recording || !this.isActive) return;

    const current = this.recording;
    this.recording = null;

    try {
      await current.stopAndUnloadAsync();
      const uri = current.getURI();
      if (uri) this._sendChunk(uri);
    } catch (e) {
      console.warn('[VoiceSession] Chunk rotate error:', e);
    }

    if (this.isActive) {
      await this._startNewChunk();
    }
  }

  async _sendChunk(uri) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.log('[VoiceSession] WS not ready, skipping chunk');
      return;
    }

    try {
      const response = await fetch(uri);
      const blob     = await response.blob();
      const reader   = new FileReader();

      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        this.ws.send(JSON.stringify({ audio_base64: base64, timestamp: Date.now() }));
        console.log('[VoiceSession] Chunk sent');
      };

      reader.onerror = (e) => console.warn('[VoiceSession] FileReader error:', e);
      reader.readAsDataURL(blob);
    } catch (e) {
      console.warn('[VoiceSession] Send chunk error:', e);
    }
  }
}

export default VoiceSession;
