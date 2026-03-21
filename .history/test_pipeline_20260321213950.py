import asyncio
import base64
import json
import os

import httpx
import numpy as np
import websockets

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
WS_BASE = os.getenv("WS_BASE", "ws://127.0.0.1:8000")
SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 250


def make_random_pcm_chunk() -> bytes:
    sample_count = int(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000.0))
    samples = np.random.randint(-12000, 12000, size=sample_count, dtype=np.int16)
    return samples.tobytes()


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        start_response = await client.post(f"{API_BASE}/sessions/start", json={"device_id": "test-device-001"})
        start_response.raise_for_status()
        started = start_response.json()
        session_id = started["session_id"]
        print(f"Started session: {session_id}")

    ws_url = f"{WS_BASE}/ws/{session_id}"
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        for _ in range(20):
            chunk = make_random_pcm_chunk()
            payload = base64.b64encode(chunk)
            await ws.send(payload)
            message = await ws.recv()
            print("INSIGHT:", message)

        await ws.send(json.dumps({"type": "stop"}))
        completion = await ws.recv()
        print("SESSION COMPLETE:")
        print(completion)

    async with httpx.AsyncClient(timeout=30.0) as client:
        details_response = await client.get(f"{API_BASE}/sessions/{session_id}")
        details_response.raise_for_status()
        full_session = details_response.json()
        print("FULL SESSION SUMMARY:")
        print(json.dumps(full_session, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
