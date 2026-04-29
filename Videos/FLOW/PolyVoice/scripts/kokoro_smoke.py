"""Generate one Kokoro TTS smoke sample through the PolyVoice SDK."""

from __future__ import annotations

import argparse
import asyncio
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polyvoice.services.tts_sdk import SDKTTSService, TTSConfig


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run a Kokoro TTS smoke sample.")
    parser.add_argument("--text", default="Hello from PolyVoice Kokoro.")
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, default=Path("kokoro_smoke.wav"))
    args = parser.parse_args()

    service = SDKTTSService(
        config=TTSConfig(
            providers=[
                {
                    "provider": "local_model",
                    "model_loader": "kokoro",
                    "name": "kokoro",
                    "language": "en",
                    "voice": args.voice,
                    "device": args.device,
                    "repo_id": "hexgrad/Kokoro-82M",
                }
            ]
        ),
        provider="kokoro",
        voice=args.voice,
        output_sample_rate=24_000,
    )

    async def text_stream():
        yield args.text

    audio = bytearray()
    await service.start()
    try:
        async for chunk in service.synthesize_stream(text_stream()):
            audio.extend(chunk.audio)
    finally:
        await service.stop()

    with wave.open(str(args.output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(bytes(audio))

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
