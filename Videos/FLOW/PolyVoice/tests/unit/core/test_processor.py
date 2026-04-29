"""Tests for the Processor base class."""

from polyvoice.core.events import VoiceEvent
from polyvoice.core.processor import Processor


class EchoProcessor(Processor):
    async def process(self, event: VoiceEvent) -> VoiceEvent | None:
        return event


async def test_processor_lifecycle_and_process() -> None:
    processor = EchoProcessor()
    event = VoiceEvent(type="ready", session_id="session-1")

    await processor.start()
    result = await processor.process(event)
    await processor.stop()

    assert result is event
    assert processor.started is False

