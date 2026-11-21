"""Validate API responses against `contracts/openapi.yaml` and `explanation.schema.json`."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"


@cache
def _spec() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text("utf-8"))
    return loaded


@cache
def _registry() -> Registry:
    explanation = json.loads((CONTRACTS / "explanation.schema.json").read_text("utf-8"))
    return Registry().with_resources(
        [
            ("explanation.schema.json", Resource.from_contents(explanation, DRAFT202012)),
            ("urn:tracex:openapi", Resource.from_contents(_spec(), DRAFT202012)),
        ]
    )


def validate(schema: str, instance: Any) -> None:
    """Raise `jsonschema.ValidationError` unless `instance` fits `components.schemas.<schema>`."""
    validator = jsonschema.Draft202012Validator(
        {"$ref": f"urn:tracex:openapi#/components/schemas/{schema}"}, registry=_registry()
    )
    validator.validate(instance)


def explanation_valid(instance: Any) -> None:
    explanation = json.loads((CONTRACTS / "explanation.schema.json").read_text("utf-8"))
    jsonschema.Draft202012Validator(explanation).validate(instance)


def spec_routes() -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, ops in _spec()["paths"].items()
        for method in ops
        if method in ("get", "post")
    }


def spec_audit_events() -> dict[tuple[str, str], str]:
    return {
        (method.upper(), path): op["x-audit-event"]
        for path, ops in _spec()["paths"].items()
        for method, op in ops.items()
        if method in ("get", "post")
    }
