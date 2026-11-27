"""Runtime check of the explanation payload against contracts/explanation.schema.json.

The payload is built by the engine and the API (read-time overlay, masking). The contract is the
promise to every client, so the final payload is validated before it leaves the API. A payload
that fails is never sent: the route answers 500 INTERNAL and an alert names the failing path.
The alert and the error carry the JSON path and the keyword only, never an instance value (a
value may be case data).
"""

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_FILE = "explanation.schema.json"


class InvalidExplanation(ValueError):
    """The payload does not fit the contract; `paths` lists where, without any values."""

    def __init__(self, paths: list[str]) -> None:
        super().__init__("explanation payload does not match the contract at " + ", ".join(paths))
        self.paths = paths


def contract_dirs() -> list[Path]:
    configured = os.environ.get("TRACEX_CONTRACTS_DIR")
    here = Path(__file__).resolve()
    found = [Path(configured)] if configured else []
    return found + [here.parents[2] / "contracts", here.parents[1] / "contracts"]


@cache
def load_schema() -> jsonschema.Draft202012Validator:
    for folder in contract_dirs():
        path = folder / SCHEMA_FILE
        if path.is_file():
            schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return jsonschema.Draft202012Validator(schema)
    raise FileNotFoundError(f"{SCHEMA_FILE} not found in {[str(p) for p in contract_dirs()]}")


def check_explanation(payload: dict[str, Any]) -> None:
    errors = sorted(load_schema().iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        paths = [
            f"{e.json_path} ({e.validator})"
            for e in errors[:5]  # keyword only, no value
        ]
        raise InvalidExplanation(paths)
