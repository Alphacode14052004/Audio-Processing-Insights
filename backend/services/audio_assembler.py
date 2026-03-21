from pathlib import Path

from pydub import AudioSegment


class AudioAssembler:
    def __init__(self) -> None:
        self._buffers: dict[str, list[bytes]] = {}

    def append_chunk(self, session_id: str, pcm_bytes: bytes) -> None:
        self._buffers.setdefault(session_id, []).append(pcm_bytes)

    def get_buffer(self, session_id: str) -> bytes:
        return b"".join(self._buffers.get(session_id, []))

    def get_duration_ms(self, session_id: str, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> float:
        raw = self.get_buffer(session_id)
        if not raw:
            return 0.0
        total_samples = len(raw) / (sample_width * channels)
        return (total_samples / sample_rate) * 1000.0

    def write_wav(self, session_id: str, output_path: str) -> None:
        raw = self.get_buffer(session_id)
        audio = AudioSegment(data=raw, sample_width=2, frame_rate=16000, channels=1)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        audio.export(output_path, format="wav")

    def clear(self, session_id: str) -> None:
        self._buffers.pop(session_id, None)


audio_assembler = AudioAssembler()
