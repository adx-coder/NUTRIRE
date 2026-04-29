"""Minimal WebSocket smoke client for a running PolyVoice server."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
from typing import Sequence

import websockets


def make_tone_pcm16(
    *,
    sample_rate: int = 16_000,
    duration_ms: int = 320,
    frequency_hz: float = 440.0,
    amplitude: float = 0.15,
) -> bytes:
    """Generate a short mono PCM16 tone."""

    sample_count = int(sample_rate * duration_ms / 1000)
    frames = bytearray()
    for index in range(sample_count):
        value = amplitude * math.sin(2.0 * math.pi * frequency_hz * index / sample_rate)
        frames.extend(struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767)))
    return bytes(frames)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Smoke-test a PolyVoice WebSocket endpoint.")
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8092/v1/ws/voice/smoke-session",
        help="WebSocket URL to connect to.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for a tts_audio_chunk.",
    )
    return parser


async def run_smoke(url: str, timeout: float) -> int:
    """Send one audio frame and print received events."""

    async with websockets.connect(url) as websocket:
        await websocket.send(make_tone_pcm16())

        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            remaining = max(0.1, deadline - asyncio.get_running_loop().time())
            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            event = json.loads(raw)
            event_type = event.get("type")
            print(event_type)
            if event_type == "tts_audio_chunk":
                return 0

    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoke client."""

    args = build_parser().parse_args(argv)
    return asyncio.run(run_smoke(args.url, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())

