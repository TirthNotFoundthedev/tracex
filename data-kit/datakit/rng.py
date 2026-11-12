"""Deterministic sub-streams. Choices use getrandbits only (data-kit spec section 10)."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class Stream:
    """One named random stream derived from the kit seed."""

    def __init__(self, seed: int, purpose: str) -> None:
        digest = hashlib.sha256(f"{seed}:{purpose}".encode()).digest()
        self._rng = random.Random(int.from_bytes(digest[:8], "big"))  # noqa: S311

    def below(self, n: int) -> int:
        """Uniform integer in [0, n) by rejection sampling."""
        if n <= 0:
            raise ValueError("n must be positive")
        bits = max(1, (n - 1).bit_length())
        while True:
            value = self._rng.getrandbits(bits)
            if value < n:
                return value

    def between(self, low: int, high: int) -> int:
        """Uniform integer in [low, high], both inclusive."""
        return low + self.below(high - low + 1)

    def chance(self, percent: int) -> bool:
        return self.below(100) < percent

    def choice(self, items: Sequence[T]) -> T:
        return items[self.below(len(items))]

    def shuffle(self, items: list[T]) -> None:
        for index in range(len(items) - 1, 0, -1):
            other = self.below(index + 1)
            items[index], items[other] = items[other], items[index]

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        pool = list(items)
        self.shuffle(pool)
        return pool[:count]

    def zipf(self, items: Sequence[T]) -> T:
        """Pick with weight 1/rank using integer arithmetic only."""
        scale = 27720  # lcm(1..12), keeps weights integral for early ranks
        weights = [scale // (rank + 1) or 1 for rank in range(len(items))]
        point = self.below(sum(weights))
        for item, weight in zip(items, weights, strict=True):
            if point < weight:
                return item
            point -= weight
        return items[-1]
