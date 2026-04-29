# Qwen3 ASR Local Smoke

Runs one WAV file through the PolyVoice ASR SDK using the `qwen3` loader.

Install the optional dependencies first:

```bash
pip install "polyvoice[qwen3-asr]"
```

Then run:

```bash
python scripts/qwen3_asr_smoke.py path/to/input.wav --device cuda --language en
```

The input must be 16-bit PCM WAV. Stereo input is mixed down to mono by the script.
