#!/usr/bin/env python3
"""Record bounded, human-reviewed figure inspiration and preferences.

This command is deliberately small and offline.  It records references,
author choices, failure reasons and promotion proposals in an append-only
hash-chained log.  It never edits a Skill, rewrites a renderer, downloads a
reference image, changes a scientific result, or pushes to GitHub.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit


SCHEMA = 1
MANIFEST_KIND = "figure-evolution-memory"
EVENT_FILE = "events.jsonl"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_JSON = 8 * 1024 * 1024
MAX_EVENTS = 100_000
REFERENCE_KINDS = {"paper", "reference-image", "palette", "layout", "other"}
FAILURE_AREAS = {"render", "layout", "legend", "semantics", "runtime", "provenance", "other"}
CLAIM_SCOPES = {"style-only", "composition-only", "style-and-composition"}


class EvolutionError(ValueError):
    """A safe, actionable memory-contract error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvolutionError(message)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    require(path.is_file() and not path.is_symlink(), f"missing or symlinked JSON file: {path}")
    require(path.stat().st_size <= MAX_JSON, f"JSON file exceeds {MAX_JSON} bytes: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (OSError, ValueError) as exc:
        raise EvolutionError(f"invalid JSON: {path}: {exc}") from exc


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise EvolutionError(f"non-finite JSON number: {value}")


def text(value: Any, label: str, *, allow_empty: bool = False, limit: int = 4096) -> str:
    require(isinstance(value, str), f"{label} must be text")
    require("\x00" not in value and len(value) <= limit, f"{label} contains invalid or oversized text")
    if not allow_empty:
        require(bool(value.strip()), f"{label} must be non-empty")
    return value


def identifier(value: Any, label: str) -> str:
    value = text(value, label)
    require(SAFE_ID.fullmatch(value) is not None, f"{label} has unsafe id: {value!r}")
    return value


def string_list(value: Any, label: str, *, allow_empty: bool = True, limit: int = 32) -> list[str]:
    require(isinstance(value, list), f"{label} must be an array")
    require(len(value) <= limit, f"{label} has too many entries")
    result = [text(item, f"{label}[{index}]", limit=256) for index, item in enumerate(value)]
    require(allow_empty or bool(result), f"{label} must be non-empty")
    return result


def local_label(value: Any, label: str) -> str:
    value = text(value, label, limit=4096)
    require("\\" not in value and not any(ord(char) < 32 for char in value), f"{label} contains unsafe path characters")
    require(not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value), f"{label} must be a local path label")
    return value


def https_url(value: Any, label: str) -> str:
    value = text(value, label, limit=4096)
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password,
            f"{label} must be a plain HTTPS URL")
    require("\x00" not in value, f"{label} contains invalid characters")
    return value


def safe_memory(path: Path) -> Path:
    path = path.expanduser().absolute()
    require(path.is_dir() and not path.is_symlink(), f"memory directory does not exist or is symlinked: {path}")
    return path


def load_manifest(memory: Path) -> dict[str, Any]:
    value = read_json(memory / "manifest.json")
    require(isinstance(value, dict), "memory manifest must be an object")
    require(value.get("schema_version") == SCHEMA and value.get("kind") == MANIFEST_KIND,
            "unsupported memory manifest")
    text(value.get("profile"), "manifest.profile")
    files = value.get("files")
    require(isinstance(files, dict) and files.get("events") == EVENT_FILE, "manifest.files.events must be events.jsonl")
    require(value.get("automatic_skill_self_edit") is False, "automatic_skill_self_edit must remain false")
    require(value.get("automatic_github_push") is False, "automatic_github_push must remain false")
    require(value.get("reference_images_are_style_only") is True, "reference_images_are_style_only must remain true")
    require(value.get("human_confirmation_required") is True, "human_confirmation_required must remain true")
    return value


def event_unsigned(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "event_sha256"}


def validate_payload(kind: str, payload: Any) -> None:
    require(isinstance(payload, dict), f"{kind} payload must be an object")
    if kind == "reference":
        identifier(payload.get("reference_id"), "reference.reference_id")
        text(payload.get("title"), "reference.title")
        require(payload.get("reference_kind") in REFERENCE_KINDS, "reference.reference_kind is invalid")
        path = payload.get("path")
        source_url = payload.get("source_url")
        require(path is not None or source_url is not None, "reference needs path or source_url")
        if path is not None:
            local_label(path, "reference.path")
        if source_url is not None:
            https_url(source_url, "reference.source_url")
        string_list(payload.get("tags", []), "reference.tags")
        require(payload.get("claim_scope") in CLAIM_SCOPES, "reference.claim_scope is invalid")
        text(payload.get("notes", ""), "reference.notes", allow_empty=True)
        if "asset_sha256" in payload:
            require(isinstance(payload["asset_sha256"], str) and HEX64.fullmatch(payload["asset_sha256"]),
                    "reference.asset_sha256 must be a SHA-256 digest")
    elif kind == "choice":
        identifier(payload.get("variant_id"), "choice.variant_id")
        text(payload.get("reason"), "choice.reason")
        string_list(payload.get("preferred_features", []), "choice.preferred_features")
        string_list(payload.get("avoided_features", []), "choice.avoided_features")
        text(payload.get("notes", ""), "choice.notes", allow_empty=True)
        if payload.get("run") is not None:
            local_label(payload["run"], "choice.run")
        if payload.get("plan_sha256") is not None:
            require(isinstance(payload["plan_sha256"], str) and HEX64.fullmatch(payload["plan_sha256"]),
                    "choice.plan_sha256 must be a SHA-256 digest")
    elif kind == "failure":
        require(payload.get("area") in FAILURE_AREAS, "failure.area is invalid")
        text(payload.get("reason"), "failure.reason")
        text(payload.get("corrective_action"), "failure.corrective_action")
        text(payload.get("artifact", ""), "failure.artifact", allow_empty=True)
        string_list(payload.get("tags", []), "failure.tags")
    elif kind == "promotion_request":
        text(payload.get("proposal"), "promotion_request.proposal")
        text(payload.get("reason"), "promotion_request.reason")
        string_list(payload.get("evidence_event_ids", []), "promotion_request.evidence_event_ids", allow_empty=False)
        require(payload.get("status") == "pending-human-review", "promotion_request.status must be pending-human-review")
        require(payload.get("apply") is False, "promotion_request.apply must remain false")
    else:
        raise EvolutionError(f"unknown event kind: {kind}")


def read_events(memory: Path) -> list[dict[str, Any]]:
    path = memory / EVENT_FILE
    require(path.is_file() and not path.is_symlink(), f"missing or symlinked event log: {path}")
    events = []
    previous = "0" * 64
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        require(line_number <= MAX_EVENTS, f"event log exceeds {MAX_EVENTS} events")
        if not line.strip():
            raise EvolutionError(f"blank event line at {line_number}")
        try:
            event = json.loads(line, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        except (ValueError, OSError) as exc:
            raise EvolutionError(f"invalid event JSON at line {line_number}: {exc}") from exc
        require(isinstance(event, dict), f"event line {line_number} must be an object")
        require(event.get("schema_version") == SCHEMA, f"event line {line_number} has unsupported schema")
        require(event.get("sequence") == line_number, f"event sequence mismatch at line {line_number}")
        identifier(event.get("event_id"), f"event[{line_number}].event_id")
        kind = text(event.get("kind"), f"event[{line_number}].kind")
        text(event.get("recorded_at"), f"event[{line_number}].recorded_at")
        text(event.get("author"), f"event[{line_number}].author")
        require(event.get("previous_event_sha256") == previous, f"event chain mismatch at line {line_number}")
        validate_payload(kind, event.get("payload"))
        stored = event.get("event_sha256")
        require(isinstance(stored, str) and HEX64.fullmatch(stored), f"event line {line_number} has invalid hash")
        require(digest(canonical(event_unsigned(event))) == stored, f"event hash mismatch at line {line_number}")
        previous = stored
        events.append(event)
    return events


def append_event(memory: Path, kind: str, payload: dict[str, Any], author: str) -> dict[str, Any]:
    load_manifest(memory)
    events = read_events(memory)
    validate_payload(kind, payload)
    sequence = len(events) + 1
    event = {
        "schema_version": SCHEMA,
        "event_id": f"{kind}-{sequence:06d}",
        "sequence": sequence,
        "kind": kind,
        "recorded_at": now(),
        "author": text(author, "author"),
        "payload": payload,
        "previous_event_sha256": events[-1]["event_sha256"] if events else "0" * 64,
    }
    event["event_sha256"] = digest(canonical(event))
    path = memory / EVENT_FILE
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
    return event


def init_memory(path: Path, profile: str) -> dict[str, Any]:
    path = path.expanduser().absolute()
    require(not path.exists() and not path.is_symlink(), f"refusing to overwrite existing path: {path}")
    path.mkdir(parents=True)
    manifest = {
        "schema_version": SCHEMA,
        "kind": MANIFEST_KIND,
        "created_at": now(),
        "profile": text(profile, "profile"),
        "files": {"events": EVENT_FILE},
        "reference_images_are_style_only": True,
        "human_confirmation_required": True,
        "automatic_skill_self_edit": False,
        "automatic_github_push": False,
        "promotion_policy": "Proposals remain pending until an author reviews and applies them manually.",
    }
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path / EVENT_FILE).write_text("", encoding="utf-8")
    (path / "README.md").write_text(
        "# Figure evolution memory\n\n"
        "This directory stores append-only, human-reviewed inspiration and preference events.\n"
        "It never edits skills, changes scientific results, downloads images, or pushes code.\n",
        encoding="utf-8",
    )
    return {"ok": True, "status": "initialized", "memory": str(path), "schema_version": SCHEMA}


def optional_asset_digest(path_label: str | None) -> str | None:
    if not path_label:
        return None
    path = Path(path_label).expanduser()
    if not path.is_file() or path.is_symlink():
        return None
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def add_reference(args) -> dict[str, Any]:
    memory = safe_memory(Path(args.memory))
    path_label_value = local_label(args.path, "path") if args.path else None
    source_url = https_url(args.source_url, "source_url") if args.source_url else None
    require(path_label_value or source_url, "provide --path or --source-url")
    payload = {
        "reference_id": identifier(args.id, "id"),
        "title": text(args.title, "title"),
        "reference_kind": args.kind,
        "path": path_label_value,
        "source_url": source_url,
        "tags": string_list(args.tags, "tags"),
        "claim_scope": args.claim_scope,
        "notes": text(args.notes or "", "notes", allow_empty=True),
    }
    asset_digest = optional_asset_digest(path_label_value)
    if asset_digest:
        payload["asset_sha256"] = asset_digest
    event = append_event(memory, "reference", payload, args.author)
    return {"ok": True, "status": "recorded", "event_id": event["event_id"], "reference_id": payload["reference_id"]}


def run_plan_digest(run: str | None) -> str | None:
    if not run:
        return None
    path = Path(run).expanduser().absolute()
    require(path.is_dir() and not path.is_symlink(), f"run directory does not exist: {path}")
    plan = path / "plan.json"
    if not plan.is_file() or plan.is_symlink():
        return None
    value = read_json(plan)
    return value.get("plan_sha256") if isinstance(value, dict) else None


def record_choice(args) -> dict[str, Any]:
    memory = safe_memory(Path(args.memory))
    payload = {
        "variant_id": identifier(args.variant_id, "variant_id"),
        "reason": text(args.reason, "reason"),
        "preferred_features": string_list(args.prefer, "prefer"),
        "avoided_features": string_list(args.avoid, "avoid"),
        "notes": text(args.notes or "", "notes", allow_empty=True),
    }
    if args.run:
        run = Path(args.run).expanduser().absolute()
        require(run.is_dir() and not run.is_symlink(), f"run directory does not exist: {run}")
        payload["run"] = str(run)
        plan_sha = run_plan_digest(str(run))
        if plan_sha:
            require(isinstance(plan_sha, str) and HEX64.fullmatch(plan_sha), "run plan hash is invalid")
            payload["plan_sha256"] = plan_sha
    event = append_event(memory, "choice", payload, args.author)
    return {"ok": True, "status": "recorded", "event_id": event["event_id"], "variant_id": payload["variant_id"]}


def record_failure(args) -> dict[str, Any]:
    memory = safe_memory(Path(args.memory))
    payload = {
        "area": args.area,
        "reason": text(args.reason, "reason"),
        "corrective_action": text(args.action, "action"),
        "artifact": text(args.artifact or "", "artifact", allow_empty=True),
        "tags": string_list(args.tags, "tags"),
    }
    event = append_event(memory, "failure", payload, args.author)
    return {"ok": True, "status": "recorded", "event_id": event["event_id"], "area": payload["area"]}


def propose_rule(args) -> dict[str, Any]:
    memory = safe_memory(Path(args.memory))
    events = read_events(memory)
    known = {event["event_id"] for event in events}
    evidence = string_list(args.evidence, "evidence", allow_empty=False)
    require(set(evidence) <= known, "promotion proposal references unknown event IDs")
    payload = {
        "proposal": text(args.proposal, "proposal"),
        "reason": text(args.reason, "reason"),
        "evidence_event_ids": evidence,
        "status": "pending-human-review",
        "apply": False,
    }
    event = append_event(memory, "promotion_request", payload, args.author)
    return {"ok": True, "status": payload["status"], "event_id": event["event_id"]}


def summary(memory: Path) -> dict[str, Any]:
    load_manifest(memory)
    events = read_events(memory)
    preferred = Counter()
    avoided = Counter()
    failures = Counter()
    references = Counter()
    pending = []
    for event in events:
        payload = event["payload"]
        if event["kind"] == "choice":
            preferred.update(payload["preferred_features"])
            avoided.update(payload["avoided_features"])
        elif event["kind"] == "failure":
            failures[payload["area"]] += 1
        elif event["kind"] == "reference":
            references[payload["reference_kind"]] += 1
        elif event["kind"] == "promotion_request":
            pending.append(event["event_id"])
    counts = Counter(event["kind"] for event in events)
    return {
        "ok": True,
        "memory": str(memory),
        "event_count": len(events),
        "by_kind": dict(sorted(counts.items())),
        "references_by_kind": dict(sorted(references.items())),
        "preferred_features": dict(preferred.most_common()),
        "avoided_features": dict(avoided.most_common()),
        "failure_areas": dict(sorted(failures.items())),
        "pending_promotion_requests": pending,
    }


def gallery(memory: Path, output: Path, include_local_previews: bool) -> dict[str, Any]:
    load_manifest(memory)
    events = read_events(memory)
    references = [event for event in events if event["kind"] == "reference"]
    cards = []
    for event in references:
        payload = event["payload"]
        preview = ""
        if include_local_previews and payload.get("path"):
            candidate = Path(payload["path"]).expanduser()
            if candidate.is_file() and not candidate.is_symlink() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                preview = f'<img src="{html.escape(candidate.absolute().as_uri(), quote=True)}" alt="{html.escape(payload["title"], quote=True)}">'
        source = ""
        if payload.get("source_url"):
            url = html.escape(payload["source_url"], quote=True)
            source = f'<a href="{url}" rel="noopener noreferrer">source</a>'
        tags = ", ".join(html.escape(tag) for tag in payload["tags"]) or "—"
        cards.append(
            "<article class=\"card\">"
            + preview
            + f"<h2>{html.escape(payload['title'])}</h2>"
            + f"<p><b>{html.escape(payload['reference_kind'])}</b> · {html.escape(payload['claim_scope'])}</p>"
            + f"<p>tags: {tags}</p>"
            + f"<p>{html.escape(payload['notes'])}</p>"
            + f"<p>event: <code>{html.escape(event['event_id'])}</code> {source}</p>"
            + "</article>"
        )
    page = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src file:;">
<title>Figure evolution references</title>
<style>
body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#202124;background:#fafafa}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}
.card{background:#fff;border:1px solid #d8dee8;border-radius:8px;padding:1rem;box-shadow:0 1px 3px #00000012}
.card img{display:block;width:100%;max-height:220px;object-fit:contain;background:#f1f3f5;margin-bottom:.75rem}
h1{font-size:1.5rem}h2{font-size:1.05rem;margin:.25rem 0 .5rem}p{font-size:.9rem;line-height:1.4;margin:.35rem 0}code{font-size:.78rem}
</style>
<h1>Figure evolution references</h1>
<p>Style and composition references only. This gallery does not change scientific results or skills.</p>
<main class="grid">""" + "".join(cards) + """</main>
"""
    output = output.expanduser().absolute()
    require(not output.exists() and not output.is_symlink(), f"refusing to overwrite gallery: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return {"ok": True, "status": "written", "output": str(output), "reference_count": len(references)}


def check(memory: Path) -> dict[str, Any]:
    load_manifest(memory)
    events = read_events(memory)
    return {"ok": True, "status": "verified", "memory": str(memory), "event_count": len(events)}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a new memory directory")
    init.add_argument("--memory", required=True, type=Path)
    init.add_argument("--profile", default="Daxuan figure preferences")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--memory", required=True, type=Path)
    common.add_argument("--author", default="Daxuan")
    check_cmd = commands.add_parser("check", parents=[common], help="verify manifest and hash chain")
    check_cmd.set_defaults(handler=check)
    summary_cmd = commands.add_parser("summary", parents=[common], help="summarize bounded memory")
    summary_cmd.set_defaults(handler=summary)

    reference = commands.add_parser("add-reference", parents=[common], help="append a style/composition reference")
    reference.add_argument("--id", required=True)
    reference.add_argument("--title", required=True)
    reference.add_argument("--kind", choices=sorted(REFERENCE_KINDS), required=True)
    reference.add_argument("--path")
    reference.add_argument("--source-url")
    reference.add_argument("--tag", dest="tags", action="append", default=[])
    reference.add_argument("--claim-scope", choices=sorted(CLAIM_SCOPES), default="style-only")
    reference.add_argument("--notes", default="")
    reference.set_defaults(handler=add_reference)

    choice = commands.add_parser("record-choice", parents=[common], help="append an author candidate choice")
    choice.add_argument("--variant-id", required=True)
    choice.add_argument("--reason", required=True)
    choice.add_argument("--run")
    choice.add_argument("--prefer", action="append", default=[])
    choice.add_argument("--avoid", action="append", default=[])
    choice.add_argument("--notes", default="")
    choice.set_defaults(handler=record_choice)

    failure = commands.add_parser("record-failure", parents=[common], help="append a failed-render or review reason")
    failure.add_argument("--area", choices=sorted(FAILURE_AREAS), required=True)
    failure.add_argument("--reason", required=True)
    failure.add_argument("--action", required=True)
    failure.add_argument("--artifact", default="")
    failure.add_argument("--tag", dest="tags", action="append", default=[])
    failure.set_defaults(handler=record_failure)

    proposal = commands.add_parser("propose-rule", parents=[common], help="record a rule proposal for human review")
    proposal.add_argument("--proposal", required=True)
    proposal.add_argument("--reason", required=True)
    proposal.add_argument("--evidence", action="append", default=[])
    proposal.set_defaults(handler=propose_rule)

    gallery_cmd = commands.add_parser("gallery", parents=[common], help="write an offline reference gallery")
    gallery_cmd.add_argument("--out", required=True, type=Path)
    gallery_cmd.add_argument("--include-local-previews", action="store_true")
    gallery_cmd.set_defaults(handler=lambda args: gallery(safe_memory(Path(args.memory)), args.out, args.include_local_previews))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_memory(args.memory, args.profile)
        else:
            result = args.handler(safe_memory(Path(args.memory))) if args.command in {"check", "summary"} else args.handler(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EvolutionError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
