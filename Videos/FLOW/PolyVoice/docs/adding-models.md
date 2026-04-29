# Adding Models

PolyVoice model support should feel like adding a small Transformers integration: one implementation file, one registry entry, one recipe or config path, one fake test, and one real smoke when the dependency is heavy.

The rule: **do not edit runtime/bootstrap for a new ASR, VAD, LLM, or TTS model.** Runtime code selects providers from config. Model-specific behavior belongs in SDK loaders, clients, providers, recipes, and tests.

## Extension Checklist

For every new model or provider:

1. Add one implementation file in the matching SDK package.
2. Register it with the SDK decorator.
3. Add or update a recipe/example config that selects it.
4. Add a fake or dependency-light unit test proving config selection works.
5. Add a real smoke script when the model needs GPU, model weights, or a live provider.
6. Keep optional imports inside `load()`, `start()`, or `initialize()` so importing PolyVoice remains cheap.
7. Raise `ServiceError` with clear install guidance when an optional dependency is missing.

## Scaffold Command

Use the scaffold script for the starter file and starter test:

```bash
python scripts/scaffold_model_loader.py --kind asr --name qwen3_large
python scripts/scaffold_model_loader.py --kind vad --name my_vad
python scripts/scaffold_model_loader.py --kind llm --name my_gateway
python scripts/scaffold_model_loader.py --kind tts --name my_voice_model
```

The script writes:

- `src/polyvoice/services/asr_sdk/models/<name>.py`
- `src/polyvoice/services/asr_sdk/vad/<name>.py`
- `src/polyvoice/services/llm_sdk/clients/<name>.py`
- `src/polyvoice/services/tts_sdk/model_loaders/<name>.py`
- a starter unit test under `tests/unit/services/...`

After scaffolding, import the module from the package `__init__.py` for built-in PolyVoice support, or from your plugin entrypoint for external support. The registry decorator runs when the module is imported.

## ASR Model Loader

ASR models implement `BaseASRModel`:

```python
@register_asr_model("my_asr")
class MyASRModel(BaseASRModel):
    async def load(self, config: dict) -> None:
        ...

    async def transcribe_chunk(
        self,
        audio: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> Sequence[ASRSegment]:
        ...

    @property
    def model_name(self) -> str:
        return "my_asr"
```

Config shape:

```python
ASRConfig(
    models=[{"name": "main", "model_loader": "my_asr"}],
    vad={"provider": "energy"},
)
```

## VAD Provider

VAD providers implement `BaseVAD`:

```python
@register_vad("my_vad")
class MyVAD(BaseVAD):
    async def load(self, config: dict) -> None:
        ...

    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        ...
```

Config shape:

```python
ASRConfig(
    models=[{"name": "main", "model_loader": "qwen3"}],
    vad={"provider": "my_vad", "threshold": 0.45},
)
```

## LLM Client

LLM clients implement `BaseLLMClient`:

```python
@register_llm_client("my_llm")
class MyLLMClient(BaseLLMClient):
    async def start(self) -> None:
        ...

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        ...

    @property
    def model_name(self) -> str:
        return str(self.config["model"])
```

Config shape:

```python
LLMConfig(
    clients=[{"name": "main", "client": "my_llm", "model": "local-model"}],
)
```

## TTS Model Loader

TTS local models implement `BaseModelLoader` and are used through the `local_model` provider:

```python
@register_model_loader("my_tts")
class MyTTSLoader(BaseModelLoader):
    CAPABILITIES = {TTSCapability.BATCH}

    async def load(self, config: dict) -> None:
        ...

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        ...

    async def unload(self) -> None:
        ...

    @property
    def native_sample_rate(self) -> int:
        return 24_000

    @property
    def loader_name(self) -> str:
        return "my_tts"
```

Config shape:

```python
TTSConfig(
    providers=[
        {
            "name": "main",
            "provider": "local_model",
            "model_loader": "my_tts",
        }
    ],
)
```

## Fake Test Pattern

Fake tests should prove that the registry and config path work without the heavy dependency:

```python
async def test_my_model_loads_from_config() -> None:
    sdk = StreamingASRSDK()
    await sdk.initialize(
        ASRConfig(models=[{"name": "main", "model_loader": "my_asr"}])
    )
    assert sdk.available_models == ["main"]
    await sdk.shutdown()
```

The golden examples live in `tests/unit/services/test_extension_contracts.py`.

## Real Smoke Pattern

Use a script when the dependency needs GPU, model weights, or a live endpoint. The smoke should:

- accept `--device`, `--model-name`, and output/input paths when relevant;
- include a fake mode when possible;
- print concise metadata;
- stop services in `finally`;
- avoid writing artifacts into git-tracked paths.

Current examples:

- `scripts/kokoro_smoke.py`
- `scripts/qwen3_asr_smoke.py`

## Optional Dependency Pattern

Import heavy dependencies inside loader startup:

```python
async def load(self, config: dict) -> None:
    try:
        import expensive_model_package
    except ImportError as exc:
        raise ServiceError(
            "My model requires `pip install -e .[my-extra]`"
        ) from exc
```

This keeps CPU-only tests fast and keeps `import polyvoice` from failing when a user has not installed every possible model backend.
