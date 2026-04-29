"""Scaffold SDK-first model, client, and VAD extensions."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

ASR_TEMPLATE = Template(
    '''"""$display_name ASR model loader."""

from __future__ import annotations

from collections.abc import Sequence

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.asr_sdk.models import BaseASRModel, register_asr_model
from polyvoice.services.asr_sdk.types import ASRRequest, ASRSegment


@register_asr_model("$slug")
class $class_name(BaseASRModel):
    """ASR loader for $display_name."""

    async def load(self, config: dict) -> None:
        """Load model resources."""

        self.config = config
        # TODO: import optional heavy dependencies here and raise ServiceError with install help.

    async def transcribe_chunk(
        self,
        audio: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> Sequence[ASRSegment]:
        """Transcribe one streaming audio chunk."""

        del request
        if not audio:
            return []
        raise ServiceError("$display_name ASR transcription is not implemented yet")

    @property
    def model_name(self) -> str:
        """Return the registered model name."""

        return "$slug"
'''
)

VAD_TEMPLATE = Template(
    '''"""$display_name VAD provider."""

from __future__ import annotations

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.asr_sdk.vad import BaseVAD, register_vad


@register_vad("$slug")
class $class_name(BaseVAD):
    """VAD provider for $display_name."""

    async def load(self, config: dict) -> None:
        """Load VAD resources."""

        self.config = config
        # TODO: import optional heavy dependencies here and raise ServiceError with install help.

    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        """Return whether this chunk contains speech."""

        del audio, sample_rate
        raise ServiceError("$display_name VAD is not implemented yet")
'''
)

LLM_TEMPLATE = Template(
    '''"""$display_name LLM client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm_sdk.clients import BaseLLMClient, register_llm_client


@register_llm_client("$slug")
class $class_name(BaseLLMClient):
    """LLM client for $display_name."""

    async def start(self) -> None:
        """Open client resources."""

        # TODO: initialize optional SDK clients here.

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream model output chunks."""

        del messages, tools, temperature, max_tokens
        raise ServiceError("$display_name LLM streaming is not implemented yet")
        yield LLMChunk(text="", is_final=True)

    @property
    def model_name(self) -> str:
        """Return the active model name."""

        return str(self.config.get("model", "$slug"))
'''
)

TTS_TEMPLATE = Template(
    '''"""$display_name TTS model loader."""

from __future__ import annotations

import numpy as np

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.tts_sdk import TTSRequest
from polyvoice.services.tts_sdk.model_loaders import BaseModelLoader, register_model_loader
from polyvoice.services.tts_sdk.models import TTSCapability


@register_model_loader("$slug")
class $class_name(BaseModelLoader):
    """TTS model loader for $display_name."""

    CAPABILITIES = {TTSCapability.BATCH}

    async def load(self, config: dict) -> None:
        """Load model resources."""

        self.config = config
        # TODO: import optional heavy dependencies here and raise ServiceError with install help.

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        """Return one complete audio array plus sample rate."""

        del text, request
        raise ServiceError("$display_name TTS synthesis is not implemented yet")

    async def unload(self) -> None:
        """Release model resources."""

    @property
    def native_sample_rate(self) -> int:
        """Native model sample rate."""

        return int(self.config.get("sample_rate", 24_000))

    @property
    def loader_name(self) -> str:
        """Registered loader name."""

        return "$slug"
'''
)

TEST_TEMPLATE = Template(
    '''"""Starter tests for the $display_name $kind extension."""

import pytest


def test_${slug}_python_module_imports() -> None:
    pytest.importorskip("$module_path")
'''
)


@dataclass(frozen=True)
class ScaffoldTarget:
    """Resolved scaffold paths and names."""

    kind: str
    slug: str
    display_name: str
    class_name: str
    module_path: str
    source_path: Path
    test_path: Path


KIND_TO_TEMPLATE = {
    "asr": ASR_TEMPLATE,
    "vad": VAD_TEMPLATE,
    "llm": LLM_TEMPLATE,
    "tts": TTS_TEMPLATE,
}

KIND_TO_PACKAGE = {
    "asr": "polyvoice.services.asr_sdk.models",
    "vad": "polyvoice.services.asr_sdk.vad",
    "llm": "polyvoice.services.llm_sdk.clients",
    "tts": "polyvoice.services.tts_sdk.model_loaders",
}

KIND_TO_SOURCE_DIR = {
    "asr": Path("src/polyvoice/services/asr_sdk/models"),
    "vad": Path("src/polyvoice/services/asr_sdk/vad"),
    "llm": Path("src/polyvoice/services/llm_sdk/clients"),
    "tts": Path("src/polyvoice/services/tts_sdk/model_loaders"),
}

KIND_TO_TEST_DIR = {
    "asr": Path("tests/unit/services/asr_sdk"),
    "vad": Path("tests/unit/services/asr_sdk"),
    "llm": Path("tests/unit/services/llm_sdk"),
    "tts": Path("tests/unit/services/tts_sdk"),
}

KIND_TO_SUFFIX = {
    "asr": "ASRModel",
    "vad": "VAD",
    "llm": "LLMClient",
    "tts": "TTSLoader",
}


def slugify(name: str) -> str:
    """Normalize a user-facing model name into a Python module slug."""

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        raise ValueError("name must contain at least one letter or number")
    if slug[0].isdigit():
        slug = f"model_{slug}"
    return slug


def class_name_for(slug: str, suffix: str) -> str:
    """Return a class name for a slug and suffix."""

    stem = "".join(part.capitalize() for part in slug.split("_"))
    return f"{stem}{suffix}"


def resolve_target(root: Path, kind: str, name: str) -> ScaffoldTarget:
    """Resolve scaffold paths for one extension."""

    slug = slugify(name)
    class_name = class_name_for(slug, KIND_TO_SUFFIX[kind])
    module_path = f"{KIND_TO_PACKAGE[kind]}.{slug}"
    return ScaffoldTarget(
        kind=kind,
        slug=slug,
        display_name=name.strip(),
        class_name=class_name,
        module_path=module_path,
        source_path=root / KIND_TO_SOURCE_DIR[kind] / f"{slug}.py",
        test_path=root / KIND_TO_TEST_DIR[kind] / f"test_{slug}.py",
    )


def render_source(target: ScaffoldTarget) -> str:
    """Render source for a scaffold target."""

    return KIND_TO_TEMPLATE[target.kind].substitute(
        slug=target.slug,
        display_name=target.display_name,
        class_name=target.class_name,
    )


def render_test(target: ScaffoldTarget) -> str:
    """Render starter test for a scaffold target."""

    return TEST_TEMPLATE.substitute(
        slug=target.slug,
        kind=target.kind,
        display_name=target.display_name,
        module_path=target.module_path,
    )


def write_file(path: Path, content: str, *, force: bool) -> None:
    """Write one scaffold file."""

    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold(root: Path, kind: str, name: str, *, force: bool) -> ScaffoldTarget:
    """Create source and starter test files."""

    target = resolve_target(root, kind, name)
    write_file(target.source_path, render_source(target), force=force)
    write_file(target.test_path, render_test(target), force=force)
    return target


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=sorted(KIND_TO_TEMPLATE))
    parser.add_argument("--name", required=True, help="Model/client/provider name to scaffold")
    parser.add_argument("--root", default=".", type=Path, help="Repository root")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    return parser


def main() -> None:
    """CLI entry point."""

    args = build_parser().parse_args()
    target = scaffold(args.root.resolve(), args.kind, args.name, force=args.force)
    print(f"created {target.source_path}")
    print(f"created {target.test_path}")
    print("next: import the module from package __init__.py or your plugin entrypoint")


if __name__ == "__main__":
    main()
