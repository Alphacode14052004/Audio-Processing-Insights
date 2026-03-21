import argparse
import asyncio
import base64
import json
import os
import wave

import httpx
import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream a WAV file through the realtime pipeline.")
    parser.add_argument(
        "--wav",
        default="backend/recordings/testingaudio.wav",
        help="Path to WAV file to stream",
    )
    parser.add_argument("--chunk-ms", type=int, default=250, help="Chunk duration in milliseconds")
    parser.add_argument("--device-id", default="wav-test-device", help="Device id for session start")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    api_base = os.getenv("API_BASE", "http://127.0.0.1:8000")
    ws_base = os.getenv("WS_BASE", "ws://127.0.0.1:8000")

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_response = await client.post(f"{api_base}/sessions/start", json={"device_id": args.device_id})
        start_response.raise_for_status()
        session_id = start_response.json()["session_id"]

    print(f"Session started: {session_id}")

    insight_count = 0
    ws_url = f"{ws_base}/ws/{session_id}"
    with wave.open(args.wav, "rb") as wav_file:
        framerate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()

        if sample_width != 2:
            raise ValueError(f"Expected 16-bit PCM WAV, got sample width {sample_width}")

        frames_per_chunk = int(framerate * (args.chunk_ms / 1000.0))
        bytes_per_chunk = frames_per_chunk * channels * sample_width
        raw_audio = wav_file.readframes(wav_file.getnframes())

    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        for offset in range(0, len(raw_audio), bytes_per_chunk):
            chunk = raw_audio[offset : offset + bytes_per_chunk]
            if not chunk:
                continue
            await ws.send(base64.b64encode(chunk))
            reply = json.loads(await ws.recv())
            if reply.get("type") == "insight":
                insight_count += 1

        await ws.send(json.dumps({"type": "stop"}))
        completion = json.loads(await ws.recv())

    print(f"Insights received: {insight_count}")
    print("Session complete payload:")
    print(json.dumps(completion, indent=2))

    async with httpx.AsyncClient(timeout=30.0) as client:
        summary = await client.get(f"{api_base}/sessions/{session_id}")
        summary.raise_for_status()
        summary_json = summary.json()

    print("Persisted session summary:")
    print(
        json.dumps(
            {
                "session_id": summary_json["id"],
                "status": summary_json["status"],
                "total_insights": summary_json["total_insights"],
                "file_path": summary_json["file_path"],
                "speakers_count": len(summary_json.get("speakers", [])),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
