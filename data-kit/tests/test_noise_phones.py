"""K3: noise phones are never one adjacent-digit swap apart (that reads as PHONE_TRANSPOSED)."""

from __future__ import annotations

from typing import Any


def swaps(phone: str) -> set[str]:
    return {
        phone[:i] + phone[i + 1] + phone[i] + phone[i + 2 :]
        for i in range(len(phone) - 1)
        if phone[i] != phone[i + 1]
    }


def test_no_two_noise_phones_are_an_adjacent_swap_apart_in_the_small_tier(
    gt: dict[str, Any],
) -> None:
    phones = {
        e["normalized"]
        for e in gt["entities"]
        if e["type"] == "PHONE" and e["gt_id"].startswith("NZ-")
    }

    assert [p for p in sorted(phones) if swaps(p) & phones] == []
