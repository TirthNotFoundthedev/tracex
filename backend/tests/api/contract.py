"""Validate API responses against `contracts/openapi.yaml` and `explanation.schema.json`."""

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"


def _open_up(node: Any, schemas: dict[str, Any]) -> None:
    """The contract extends strict objects with `allOf`, which no validator can satisfy
    (`additionalProperties: false` in a member rejects the other members' properties). For
    validation only, each `allOf` member loses `additionalProperties` and the composite becomes
    `unevaluatedProperties: false`, which says what the contract means."""
    if isinstance(node, list):
        for item in node:
            _open_up(item, schemas)
        return
    if not isinstance(node, dict):
        return
    for value in list(node.values()):
        _open_up(value, schemas)
    members = node.get("allOf")
    if isinstance(members, list) and "unevaluatedProperties" not in node:
        opened = []
        for member in members:
            target = member
            if "$ref" in member and member["$ref"].startswith("#/components/schemas/"):
                target = schemas[member["$ref"].rsplit("/", 1)[-1]]
            if isinstance(target, dict) and "properties" in target or "allOf" in target:
                member = copy.deepcopy(target)
                member.pop("additionalProperties", None)
                member.pop("unevaluatedProperties", None)
            opened.append(member)
        node["allOf"] = opened
        node["unevaluatedProperties"] = False


@cache
def _spec() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text("utf-8"))
    schemas = loaded["components"]["schemas"]
    for schema in schemas.values():
        _open_up(schema, schemas)
    return loaded


@cache
def _raw_spec() -> dict[str, Any]:
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
        for path, ops in _raw_spec()["paths"].items()
        for method in ops
        if method in ("get", "post")
    }


def spec_audit_events() -> dict[tuple[str, str], str]:
    return {
        (method.upper(), path): op["x-audit-event"]
        for path, ops in _raw_spec()["paths"].items()
        for method, op in ops.items()
        if method in ("get", "post")
    }
