"""Seed files: case assignments derived from users.json (data-kit spec section 9)."""

from __future__ import annotations

import json

from datakit.pools import KIT_ROOT
from datakit.rng import Stream

DISTRICT_DIGIT = {"Rivergate": 1, "Hillcrest": 2, "Lakeside": 3, "Rampur": 4}
NOISE_PER_USER = 3
NOISE_WINDOW = 15


def case_assignments_csv(seed: int) -> str:
    """username,case_id rows: planted assignments plus 3 noise cases per district user.

    Noise cases come from the first 15 of each district, which exist in every tier.
    """
    users = json.loads((KIT_ROOT / "seed" / "users.json").read_text("utf-8"))["users"]
    rows = ["username,case_id"]
    for user in users:
        for case_id in user["assigned_cases"]:
            rows.append(f"{user['username']},{case_id}")
        if not user["active"] or user["role"] in ("ADMIN", "SENIOR") or not user["districts"]:
            continue
        digit = DISTRICT_DIGIT[user["districts"][0]]
        stream = Stream(seed, f"assign:{user['username']}")
        pool = [f"C-{digit}{50 + i}" for i in range(NOISE_WINDOW)]
        for case_id in sorted(stream.sample(pool, NOISE_PER_USER), key=lambda c: int(c[3:])):
            rows.append(f"{user['username']},{case_id}")
    return "\n".join(rows) + "\n"
