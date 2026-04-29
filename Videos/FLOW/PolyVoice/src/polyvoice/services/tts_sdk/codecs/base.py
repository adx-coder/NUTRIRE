"""Base codec contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseCodec(ABC):
    """Decode model output into raw audio arrays."""

    async def load(self, config: dict) -> None:
        """Load codec resources."""

    @abstractmethod
    async def decode(self, data: np.ndarray) -> np.ndarray:
        """Decode model output."""

    async def unload(self) -> None:
        """Release codec resources."""

