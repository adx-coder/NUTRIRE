"""Transcribe one WAV file through the PolyVoice Qwen3 ASR SDK loader."""

from __future__ import annotations

import argparse
import asyncio
import sys
import types
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polyvoice.core.exceptions import PolyVoiceError
from polyvoice.services.asr_sdk import ASRConfig, SDKSTTService


def _read_pcm16_wav(path: Path) -> tuple[bytes, int]:
    """Read a mono/stereo 16-bit PCM WAV file."""

    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV input is supported")
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        pcm = wav.readframes(wav.getnframes())

    if channels == 1:
        return pcm, sample_rate
    if channels == 2:
        mono = bytearray()
        for index in range(0, len(pcm), 4):
            left = int.from_bytes(pcm[index : index + 2], "little", signed=True)
            right = int.from_bytes(pcm[index + 2 : index + 4], "little", signed=True)
            mixed = int((left + right) / 2)
            mono.extend(mixed.to_bytes(2, "little", signed=True))
        return bytes(mono), sample_rate
    raise ValueError(f"Unsupported channel count: {channels}")


def _generate_pcm16_tone(*, sample_rate: int = 16_000, seconds: float = 1.0) -> tuple[bytes, int]:
    """Generate a small tone for fake-loader smoke validation."""

    t = np.linspace(0.0, seconds, int(sample_rate * seconds), endpoint=False)
    audio = 0.2 * np.sin(2.0 * np.pi * 440.0 * t)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
    return pcm.tobytes(), sample_rate


def _install_fake_qwen_asr() -> None:
    """Install a fake qwen_asr module matching the loader contract."""

    module = types.ModuleType("qwen_asr")

    class Qwen3ASRModel:
        class LLM:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def transcribe(self, *, audio, language=None, return_time_stamps=False):
                del audio, return_time_stamps
                return [
                    type(
                        "Result",
                        (),
                        {
                            "text": "hello from fake qwen3",
                            "language": language or "en",
                        },
                    )()
                ]

    module.Qwen3ASRModel = Qwen3ASRModel
    sys.modules["qwen_asr"] = module


async def _run(args: argparse.Namespace) -> int:
    if args.fake_qwen_asr:
        _install_fake_qwen_asr()

    if args.input is None:
        if not args.fake_qwen_asr:
            print("input is required unless --fake-qwen-asr is used", file=sys.stderr)
            return 2
        audio, sample_rate = _generate_pcm16_tone()
    else:
        audio, sample_rate = _read_pcm16_wav(args.input)

    service = SDKSTTService(
        config=ASRConfig(
            models=[
                {
                    "model_loader": "qwen3",
                    "name": "qwen3",
                    "model_name": args.model,
                    "sample_rate": sample_rate,
                    "language": args.language,
                    "device": args.device,
                    "gpu_memory_utilization": args.gpu_memory_utilization,
                    "max_model_len": args.max_model_len,
                    "max_inference_batch_size": args.max_inference_batch_size,
                    "max_new_tokens": args.max_new_tokens,
                }
            ],
            processing={
                "min_finalization_confidence": args.min_confidence,
            },
        ),
        model="qwen3",
        sample_rate=sample_rate,
    )

    async def audio_stream():
        yield audio

    try:
        await service.start()
        async for result in service.transcribe_stream(
            audio_stream(),
            sample_rate=sample_rate,
            language=args.language,
        ):
            print(
                {
                    "text": result.text,
                    "is_final": result.is_final,
                    "confidence": result.confidence,
                    "metadata": result.metadata,
                }
            )
    except PolyVoiceError as exc:
        print(f"ASR smoke failed: {exc}", file=sys.stderr)
        return 2
    finally:
        await service.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Qwen3 ASR smoke transcription.")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="16-bit PCM WAV file to transcribe. Optional with --fake-qwen-asr.",
    )
    parser.add_argument(
        "--fake-qwen-asr",
        action="store_true",
        help="Inject a fake qwen_asr module to validate the SDK path without GPU deps.",
    )
    parser.add_argument("--model", default="Qwen/Qwen3-ASR-0.6B")
    parser.add_argument("--language", default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.08)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-inference-batch-size", type=int, default=32)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--min-confidence", type=float, default=0.0)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
