"""One-command demo seed: synthetic cases through the real upload path (decision D63).

The seed is an API client. It signs in as the seeded admin, uploads the data-kit cases with
`POST /uploads` (so access checks, provenance and audit rows happen as in production), waits for
ingest, starts one matching run, then assigns cases to officers through the four-eyes
`/pending-changes` flow (admin proposes, a senior approves). It never connects to the database
and never writes an audit row itself: every row is written by the API for the signed-in actor
(the seeded admin and the seeded all-state senior).

The users and police areas come from `python -m tracex_api.seed` (the `migrate` service).

    python -m tracex_api.seed_demo --api-url http://api:8000 --data-kit /data-kit

Passwords are read from `TRACEX_SEED_PASSWORD_<USERNAME>`; nothing is stored here. The seed
runs only when `TRACEX_ENV` is exactly development, local, test or demo and
`TRACEX_ALLOW_DEV_SECRETS` is 1.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tracex_api.seed import load_seed

ADMIN_USER = "hari"
APPROVER_USER = "meena"  # SENIOR with all-state coverage: can approve any assignment
ALLOWED_ENVIRONMENTS = ("development", "local", "test", "demo")
ALLOW_DEV_SECRETS = "TRACEX_ALLOW_DEV_SECRETS"
FILE_ORDER = ("fir", "notes", "sdr", "cdr", "bank")
POLL_SECONDS = 1.0
EXIT_OK, EXIT_FAILED, EXIT_REFUSED = 0, 1, 2


class SeedError(RuntimeError):
    """The seed cannot continue; the message is shown to the operator."""


class SeedRefused(SeedError):
    """The environment is not one the demo seed may run in."""


class Http(Protocol):
    """The one call the seed needs. The real client uses urllib; tests plug in a TestClient."""

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: Any = None,
        form: Mapping[str, str] | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> tuple[int, Any]: ...


def refuse_if_production(env: Mapping[str, str]) -> None:
    """Run only for an exact allow-listed `TRACEX_ENV` and only with the dev-secrets flag set to 1.

    The flag is the second check: the API refuses its own dev placeholder secrets without it, and a
    real deployment never sets it.
    """
    value = env.get("TRACEX_ENV", "")
    if value not in ALLOWED_ENVIRONMENTS:
        shown = repr(value) if value else "unset"
        raise SeedRefused(
            f"TRACEX_ENV is {shown}; the demo seed runs only when it is exactly one of "
            + ", ".join(ALLOWED_ENVIRONMENTS)
        )
    if env.get(ALLOW_DEV_SECRETS, "") != "1":
        raise SeedRefused(f"{ALLOW_DEV_SECRETS} is not 1; the demo seed is for local use only")


def multipart(form: Mapping[str, str], files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in form.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            + value.encode()
            + b"\r\n"
        )
    for file_name, data in files:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
            f'filename="{file_name}"\r\nContent-Type: text/plain\r\n\r\n'.encode()
            + data
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201
        raise SeedError(f"the API answered with a redirect ({code}); the seed does not follow it")


_OPENER = urllib.request.build_opener(_NoRedirect)


class UrllibHttp:
    def __init__(self, base_url: str) -> None:
        if urllib.parse.urlsplit(base_url).scheme not in ("http", "https"):
            raise SeedError("the API URL must start with http:// or https://")
        self.base = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: Any = None,
        form: Mapping[str, str] | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> tuple[int, Any]:
        headers: dict[str, str] = {}
        data: bytes | None = None
        if files is not None:
            data, headers["Content-Type"] = multipart(form or {}, files)
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(  # noqa: S310 - URL comes from the operator, http(s) only
            self.base + path, data=data, method=method, headers=headers
        )
        try:
            with _OPENER.open(req, timeout=300) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        return status, (json.loads(raw) if raw else None)


@dataclass
class Session:
    http: Http
    token: str

    def call(
        self, method: str, path: str, *, expect: int | tuple[int, ...] = 200, **kwargs: Any
    ) -> Any:
        status, payload = self.http.request(method, path, token=self.token, **kwargs)
        ok = (expect,) if isinstance(expect, int) else expect
        if status not in ok:
            code = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
            raise SeedError(f"{method} {path} returned {status} {code or ''}".strip())
        return payload


def login(http: Http, username: str, env: Mapping[str, str]) -> Session:
    password = env.get(f"TRACEX_SEED_PASSWORD_{username.upper()}", "")
    if not password:
        raise SeedError(f"TRACEX_SEED_PASSWORD_{username.upper()} is not set")
    status, payload = http.request(
        "POST", "/auth/login", body={"username": username, "password": password}
    )
    if status != 200:
        raise SeedError(f"login as {username} failed with status {status}")
    return Session(http, payload["access_token"])


# ----------------------------------------------------------------------------------------------
# the dataset


@dataclass(frozen=True)
class CaseFiles:
    case_number: str
    digit: str
    files: list[tuple[str, bytes]]


def file_rank(name: str) -> tuple[int, str]:
    stem = name.split(".")[0]
    kind = stem.split("-")[0]
    return (FILE_ORDER.index(kind) if kind in FILE_ORDER else len(FILE_ORDER), stem)


def read_cases(dataset: Path) -> list[CaseFiles]:
    """Every case under `batches/`, baseline files first, then late-arriving ones."""
    found: dict[str, list[tuple[str, tuple[int, str], bytes]]] = {}
    for batch in sorted((dataset / "batches").iterdir()):
        for case_dir in sorted((batch / "cases").iterdir()):
            bucket = found.setdefault(case_dir.name, [])
            for path in sorted(case_dir.iterdir(), key=lambda p: file_rank(p.name)):
                bucket.append((path.name, file_rank(path.name), path.read_bytes()))
    cases = [
        CaseFiles(number, number.split("-")[1][0], [(n, d) for n, _, d in items])
        for number, items in found.items()
    ]
    cases.sort(key=lambda c: (c.digit, int(c.case_number.split("-")[1][1:])))
    return cases


def generate_dataset(data_kit: Path, tier: str, out: Path) -> Path:
    """Run the data-kit generator (stdlib only) into `out`; the kit itself is never changed."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-m", "datakit", "generate", "--tier", tier, "--out", str(out)],
        cwd=data_kit,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        raise SeedError(f"data-kit generate failed: {result.stderr.strip()[-300:]}")
    return out


# ----------------------------------------------------------------------------------------------
# the steps


def paged(session: Session, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        query = f"{path}?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = session.call("GET", query)
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            return items


def seeded_state(admin: Session, expected_files: int) -> str:
    """`none`, `done` or `partial`, from what the API already holds."""
    batches = paged(admin, "/uploads")
    runs = paged(admin, "/matching/runs")
    if not batches:
        return "none"
    ok = [b for b in batches if b["status"] == "DONE"]
    ran = any(r["status"] == "SUCCEEDED" for r in runs)
    return "done" if len(ok) >= expected_files and ran else "partial"


def upload_cases(
    admin: Session, cases: list[CaseFiles], districts: Mapping[str, str], log: Any
) -> None:
    for number, case in enumerate(cases, start=1):
        admin.call(
            "POST",
            "/uploads",
            expect=202,
            form={"case_number": case.case_number, "district_id": districts[case.digit]},
            files=case.files,
        )
        if number % 20 == 0:
            log(f"uploaded {number} of {len(cases)} cases")


def wait_for_ingest(admin: Session, timeout: float, sleep: Any = time.sleep) -> int:
    deadline = time.monotonic() + timeout
    while True:
        batches = paged(admin, "/uploads")
        if all(b["status"] in ("DONE", "FAILED") for b in batches):
            failed = [b for b in batches if b["status"] == "FAILED"]
            if failed:
                codes = sorted({str(b["error_code"]) for b in failed})
                raise SeedError(f"{len(failed)} uploaded files failed: {', '.join(codes)}")
            return len(batches)
        if time.monotonic() > deadline:
            raise SeedError("ingest did not finish in time")
        sleep(POLL_SECONDS)


def run_matching(admin: Session) -> dict[str, Any]:
    run: dict[str, Any] = admin.call("POST", "/matching/runs", expect=(200, 202), body={})
    if run["status"] != "SUCCEEDED":
        raise SeedError(f"matching run ended {run['status']} {run.get('error_code') or ''}")
    return run


def assign_cases(
    admin: Session, approver: Session, pairs: list[tuple[str, str]], case_numbers: set[str]
) -> int:
    """Four-eyes: the admin proposes each assignment and the senior approves the change hash."""
    users = {u["username"]: u["user_id"] for u in paged(admin, "/users")}
    count = 0
    for username, case_number in pairs:
        if case_number not in case_numbers or username not in users:
            continue
        change = admin.call(
            "POST",
            "/pending-changes",
            expect=201,
            body={
                "kind": "ASSIGNMENT_ADD",
                "subject_user_id": users[username],
                "new_value": {"case_number": case_number},
            },
        )
        approver.call(
            "POST",
            f"/pending-changes/{change['change_id']}/approve",
            body={"change_hash": change["change_hash"]},
        )
        count += 1
    return count


def jurisdiction_ids(admin: Session, seed_dir: Path) -> dict[str, str]:
    """Map a case-number district digit (`C-2xx` gives `2`) to the district id in the API."""
    jurisdictions, _, _ = load_seed(seed_dir)
    by_name = {
        d["name"]: d["district_id"]
        for state in admin.call("GET", "/jurisdictions")["items"]
        for d in state["districts"]
    }
    return {
        str(d["id_digit"]): by_name[d["name"]]
        for state in jurisdictions["states"]
        for d in state["districts"]
    }


def seed_demo(
    http: Http,
    env: Mapping[str, str],
    dataset: Path,
    seed_dir: Path,
    log: Any,
    ingest_timeout: float = 600,
) -> str:
    refuse_if_production(env)
    cases = read_cases(dataset)
    expected_files = sum(len(c.files) for c in cases)
    admin = login(http, ADMIN_USER, env)
    state = seeded_state(admin, expected_files)
    if state == "done":
        log("already seeded")
        return "already seeded"
    if state == "partial":
        raise SeedError(
            "the database holds part of a seed; remove the volumes "
            "(docker compose down -v) and run the seed again"
        )
    log(f"uploading {len(cases)} cases ({expected_files} files)")
    upload_cases(admin, cases, jurisdiction_ids(admin, seed_dir), log)
    wait_for_ingest(admin, ingest_timeout)
    log("ingest done; starting the matching run")
    run = run_matching(admin)
    _, _, pairs = load_seed(seed_dir)
    approver = login(http, APPROVER_USER, env)
    assigned = assign_cases(admin, approver, pairs, {c.case_number for c in cases})
    message = (
        f"seeded {len(cases)} cases, run {run['run_id']} "
        f"(auto {run['auto_created']}, suggested {run['suggested_created']}), "
        f"{assigned} case assignments"
    )
    log(message)
    return message


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    source = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Load the synthetic demo cases through the API.")
    parser.add_argument("--api-url", default=source.get("TRACEX_API_URL", "http://localhost:8000"))
    parser.add_argument("--data-kit", type=Path, default=Path("data-kit"))
    parser.add_argument("--seed-dir", type=Path, default=None)
    parser.add_argument("--tier", choices=("small", "demo"), default="small")
    parser.add_argument("--dataset", type=Path, default=None, help="use an existing kit output")
    args = parser.parse_args(argv)

    def log(line: str) -> None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    try:
        refuse_if_production(source)
        seed_dir = args.seed_dir or args.data_kit / "seed"
        with tempfile.TemporaryDirectory(prefix="tracex-demo-") as scratch:
            dataset = args.dataset or generate_dataset(
                args.data_kit, args.tier, Path(scratch) / args.tier
            )
            seed_demo(UrllibHttp(args.api_url), source, dataset, seed_dir, log)
    except SeedError as exc:
        sys.stderr.write(f"seed failed: {exc}\n")
        return EXIT_REFUSED if isinstance(exc, SeedRefused) else EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
