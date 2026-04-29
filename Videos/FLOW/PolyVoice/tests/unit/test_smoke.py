"""Smoke tests for the PolyVoice package."""


def test_import_polyvoice() -> None:
    import polyvoice

    assert polyvoice.PolyVoiceError.__name__ == "PolyVoiceError"

