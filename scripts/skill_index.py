#!/usr/bin/env python3
"""Read-only discovery of local figure skills; output candidates, never execute them.

Python 3.10+, standard library only. Catalog paths are relative to the user's
home; a leading .codex is remapped when CODEX_HOME is configured. With explicit
--root, catalog paths may alternatively be relative to that exact root. This
allows isolated catalogs without matching unrelated skills by name.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

SKIP_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}


def absolute(path: Path) -> Path:
    """Keep symlink aliases visible while removing relative path components."""
    return Path(os.path.abspath(path.expanduser()))


def default_roots() -> list[Path]:
    home = Path.home()
    codex = absolute(Path(os.environ.get("CODEX_HOME", str(home / ".codex"))))
    roots = [codex / "skills", home / ".agents" / "skills"]
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        project = [parent / ".agents" / "skills", parent / ".codex" / "skills"]
        if any(path.is_dir() for path in project):
            roots.extend(project)
            break
    roots.append(codex / "plugins" / "cache")
    return list(dict.fromkeys(absolute(path) for path in roots))


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return str(json.loads(value))
        except (ValueError, TypeError):
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return re.sub(r"\s+#.*$", "", value).strip()


def parse_metadata(text: str, directory_name: str) -> dict[str, Any]:
    """Extract name/description without evaluating YAML or assuming valid YAML."""
    lines = text.lstrip("\ufeff").splitlines()
    warnings: list[str] = []
    fields: dict[str, str] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            end = min(len(lines), 100)
            warnings.append("frontmatter_unclosed")
        else:
            body_start = end + 1
        active = None
        pieces: list[str] = []

        def finish() -> None:
            if active is not None:
                fields[active] = scalar(" ".join(pieces))

        for line in lines[1:end]:
            match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if match:
                finish()
                active = match.group(1)
                first = match.group(2).strip()
                pieces = [] if first in ("|", ">", "|-", ">-", "|+", ">+") else [first]
            elif active is not None and line[:1].isspace():
                pieces.append(line.strip())
            elif line.strip() and not line.lstrip().startswith("#"):
                warnings.append("frontmatter_nonstandard_line")
        finish()
    else:
        warnings.append("frontmatter_missing")
    name = fields.get("name", "").strip() or directory_name
    description = fields.get("description", "").strip()
    if not fields.get("name", "").strip():
        warnings.append("name_fallback_directory")
    if not description:
        warnings.append("description_missing")
        paragraph: list[str] = []
        for line in lines[body_start:]:
            if not line.strip() and paragraph:
                break
            if line.strip() and not line.lstrip().startswith(("#", "---")):
                paragraph.append(line.strip())
        description = " ".join(paragraph)[:2000]
    return {"name": name, "description": description, "metadata_warnings": sorted(set(warnings))}


def scan_paths(roots: list[Path]) -> tuple[list[Path], list[dict[str, str]]]:
    """Follow symlink directories, reject ancestry cycles, retain alias paths."""
    found: set[Path] = set()
    warnings: list[dict[str, str]] = []
    for root in roots:
        if root.is_file():
            if root.name == "SKILL.md":
                found.add(root)
            continue
        if not root.is_dir():
            continue
        stack: list[tuple[Path, frozenset[Path]]] = [(root, frozenset())]
        while stack:
            directory, ancestors = stack.pop()
            try:
                real = directory.resolve(strict=True)
                if real in ancestors:
                    warnings.append({"path": str(directory), "reason": "symlink_cycle_skipped"})
                    continue
                ancestry = ancestors | {real}
                with os.scandir(directory) as iterator:
                    children = sorted(iterator, key=lambda item: item.name)
                for child in children:
                    path = directory / child.name
                    try:
                        if child.is_file(follow_symlinks=True) and child.name == "SKILL.md":
                            found.add(path)
                        elif child.name not in SKIP_DIRECTORIES and child.is_dir(follow_symlinks=True):
                            stack.append((path, ancestry))
                    except OSError as exc:
                        warnings.append({"path": str(path), "reason": type(exc).__name__})
            except (OSError, RuntimeError) as exc:
                warnings.append({"path": str(directory), "reason": type(exc).__name__})
    return sorted(found, key=str), warnings


def load_catalog(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": None, "entries": [], "warning": "catalog_missing"}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("catalog must be an object with an entries array")
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ValueError("every catalog entry needs an id")
    return data


def mapped_home_path(relative: str) -> Path:
    path = Path(relative).expanduser()
    if path.is_absolute():
        return absolute(path)
    parts = path.parts
    if parts and parts[0] == ".codex":
        codex = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        return absolute(codex.joinpath(*parts[1:]))
    return absolute(Path.home() / path)


def catalog_targets(entry: dict[str, Any], roots: list[Path], explicit_roots: bool) -> list[Path]:
    targets: list[Path] = []
    for relative in entry.get("relative_paths", []):
        targets.append(mapped_home_path(relative))
        if explicit_roots and not Path(relative).is_absolute():
            targets.extend(root / relative for root in roots if not root.is_file())
    return list(dict.fromkeys(absolute(path) for path in targets))


def same_path(left: Path, right: Path) -> bool:
    if left == right:
        return True
    try:
        return left.resolve() == right.resolve()
    except (OSError, RuntimeError):
        return False


def installation(path: Path, entries: list[dict[str, Any]], digest: str, roots: list[Path], explicit_roots: bool) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    seen: set[tuple[str, bool]] = set()
    for entry in entries:
        for check in entry.get("resource_checks", []):
            relative = str(check.get("path", ""))
            required = bool(check.get("required", False))
            if (relative, required) in seen:
                continue
            seen.add((relative, required))
            resource = absolute(path.parent / relative)
            resources.append({
                "path": str(resource), "relative_path": relative,
                "exists": resource.exists(), "required": required,
                "notes": check.get("notes", ""),
            })
    missing = [item for item in resources if item["required"] and not item["exists"]]
    resource_state = "missing_required" if missing else ("checked_present" if resources else "not_declared")
    if resources and not missing and any(not item["exists"] for item in resources):
        resource_state = "missing_optional"
    expected_hashes = {
        entry.get("source_hashes", {})[relative]
        for entry in entries for relative in entry.get("relative_paths", [])
        if relative in entry.get("source_hashes", {})
        and any(same_path(path, target) for target in catalog_targets({"relative_paths": [relative]}, roots, explicit_roots))
    }
    source_state = "unchanged" if digest in expected_hashes else ("changed_since_review" if expected_hashes else "untracked")
    registration = "unreviewed" if not entries else ("reviewed" if source_state == "unchanged" else "review_required")
    return {
        "skill_path": str(path), "catalog_ids": sorted(entry["id"] for entry in entries),
        "registration": registration, "source_state": source_state,
        "resources": resources, "resource_state": resource_state, "runtime": "untested",
    }


def discover(roots: list[Path], catalog: dict[str, Any], explicit_roots: bool) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    paths, warnings = scan_paths(roots)
    bindings = [(entry, catalog_targets(entry, roots, explicit_roots)) for entry in catalog["entries"]]
    groups: dict[str, dict[str, Any]] = {}
    router_skill = Path(__file__).resolve().parent.parent / "SKILL.md"
    for path in paths:
        if same_path(path, router_skill):
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            warnings.append({"path": str(path), "reason": type(exc).__name__})
            continue
        digest = hashlib.sha256(raw).hexdigest()
        metadata = parse_metadata(raw.decode("utf-8", errors="replace"), path.parent.name)
        if metadata["name"] == "daxuan-figure-router":
            continue
        entries = [entry for entry, targets in bindings if any(same_path(path, target) for target in targets)]
        group = groups.setdefault(digest, {
            **metadata, "content_sha256": digest, "installations": [], "catalog_entries": [],
            "aliases": [], "directory_names": [],
        })
        group["installations"].append(installation(path, entries, digest, roots, explicit_roots))
        group["directory_names"].append(path.parent.name)
        group["aliases"].append(metadata["name"])
        existing = {entry["id"] for entry in group["catalog_entries"]}
        group["catalog_entries"].extend(entry for entry in entries if entry["id"] not in existing)
    candidates: list[dict[str, Any]] = []
    for group in groups.values():
        entries = sorted(group["catalog_entries"], key=lambda entry: entry["id"])
        group["catalog_entries"] = entries
        group["id"] = entries[0]["id"] if entries else "unreviewed-" + group["content_sha256"][:12]
        group["catalog_ids"] = [entry["id"] for entry in entries]
        registrations = {item["registration"] for item in group["installations"]}
        group["registration"] = "review_required" if "review_required" in registrations else ("reviewed" if "reviewed" in registrations else "unreviewed")
        source_states = {item["source_state"] for item in group["installations"]}
        group["source_state"] = "changed_since_review" if "changed_since_review" in source_states else ("unchanged" if "unchanged" in source_states else "untracked")
        group["runtime"] = "untested"
        group["skill_paths"] = sorted(item["skill_path"] for item in group["installations"])
        group["skill_path"] = group["skill_paths"][0]
        group["read_first_options"] = group["skill_paths"]
        group["read_first_instruction"] = "Choose one installation; read its SKILL.md and required resources before deciding."
        group["directory_names"] = sorted(set(group["directory_names"]))
        group["aliases"] = sorted(set(group["aliases"] + group["directory_names"] + [
            value for entry in entries for value in [entry.get("name", ""), *entry.get("aliases", [])] if value
        ]))
        for field in ("languages", "domains", "task_tags"):
            group[field] = sorted({value for entry in entries for value in entry.get(field, [])})
        group["roles"] = sorted({entry["role"] for entry in entries if entry.get("role")})
        group["families"] = sorted({entry["family"] for entry in entries if entry.get("family")})
        candidates.append(group)
    return sorted(candidates, key=lambda item: (item["name"].casefold(), item["id"])), warnings


def list_value(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def matches_filters(candidate: dict[str, Any], args: argparse.Namespace) -> bool:
    filtering = args.language != "any" or args.role or args.tag or args.domain
    if not filtering:
        return True
    for entry in candidate["catalog_entries"]:
        languages = {str(value).casefold() for value in entry.get("languages", [])}
        if args.language != "any" and args.language.casefold() not in languages and "language-independent" not in languages:
            continue
        if args.role and entry.get("role") != args.role:
            continue
        tags = {str(value).casefold() for value in entry.get("task_tags", [])}
        domains = {str(value).casefold() for value in entry.get("domains", [])}
        if any(tag.casefold() not in tags for tag in args.tag):
            continue
        if any(domain.casefold() not in domains for domain in args.domain):
            continue
        return True
    return False


def search_score(candidate: dict[str, Any], query: str) -> tuple[int, list[str]]:
    terms = list(dict.fromkeys(re.findall(r"[\w-]+", query.casefold())))
    fields = [
        (" ".join([candidate["name"], *candidate["aliases"], *candidate["catalog_ids"]]), 5),
        (" ".join([*candidate["domains"], *candidate["task_tags"]]), 4),
        (candidate["description"], 3),
        (" ".join(part for entry in candidate["catalog_entries"] for part in list_value(entry.get("when", ""))), 2),
    ]
    matched: set[str] = set()
    score = 0
    for value, weight in fields:
        haystack = value.casefold()
        hits = [term for term in terms if term in haystack]
        score += len(hits) * weight
        matched.update(hits)
    return score, sorted(matched)


def doctor(candidates: list[dict[str, Any]], catalog: dict[str, Any], roots: list[Path], explicit_roots: bool) -> dict[str, Any]:
    bound = {identifier for candidate in candidates for identifier in candidate["catalog_ids"]}
    names: dict[str, list[str]] = {}
    families: dict[str, list[str]] = {}
    for candidate in candidates:
        names.setdefault(candidate["name"], []).append(candidate["id"])
        for family in candidate["families"]:
            families.setdefault(family, []).append(candidate["id"])
    return {
        "runtime": "untested",
        "resource_checks_are_runtime_tests": False,
        "counts": {
            "unique_contents": len(candidates),
            "installations": sum(len(item["installations"]) for item in candidates),
            "reviewed_candidates": sum(item["registration"] == "reviewed" for item in candidates),
            "review_required_candidates": sum(item["registration"] == "review_required" for item in candidates),
            "unreviewed_candidates": sum(item["registration"] == "unreviewed" for item in candidates),
        },
        "catalog_not_discovered": [
            {"id": entry["id"], "status": "not_found_in_scanned_roots",
             "expected_paths": [str(path) for path in catalog_targets(entry, roots, explicit_roots)]}
            for entry in catalog["entries"] if entry["id"] not in bound
        ],
        "resource_issues": [
            {"id": candidate["id"], **item}
            for candidate in candidates for item in candidate["installations"]
            if item["resource_state"] in ("missing_required", "missing_optional")
        ],
        "same_name_different_contents": {name: ids for name, ids in names.items() if len(ids) > 1},
        "content_duplicates": [
            {"id": item["id"], "paths": item["skill_paths"]}
            for item in candidates if len(item["skill_paths"]) > 1
        ],
        "family_variants": {family: ids for family, ids in families.items() if len(ids) > 1},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    def add_options(target: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
        def default(value: Any) -> Any:
            return argparse.SUPPRESS if suppress_defaults else value

        target.add_argument("--root", action="append", default=default([]), help="Scan only these roots; repeatable")
        target.add_argument("--catalog", type=Path, default=default(Path(__file__).resolve().parent.parent / "references" / "capabilities.json"))
        target.add_argument("--limit", type=int, default=default(5), help="Maximum search candidates (default: 5)")
        target.add_argument("--language", type=str.lower, choices=["r", "python", "matlab", "any"], default=default("any"))
        target.add_argument("--role", choices=["primary", "helper", "reference", "maintenance"], default=default(None))
        target.add_argument("--tag", action="append", default=default([]))
        target.add_argument("--domain", action="append", default=default([]))

    add_options(parser)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List discovered candidates")
    search = commands.add_parser("search", help="Retrieve candidates; does not choose a skill")
    search.add_argument("query", nargs="*", help="Free text (omit to browse with filters)")
    show = commands.add_parser("show", help="Show every match for an id, name, alias, or directory name")
    show.add_argument("identifier")
    checking = commands.add_parser("doctor", help="Inspect paths, duplicates and declared resources only")
    for command_parser in (listing, search, show, checking):
        add_options(command_parser, suppress_defaults=True)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    roots = list(dict.fromkeys(absolute(Path(path)) for path in args.root)) if args.root else default_roots()
    try:
        catalog = load_catalog(absolute(args.catalog))
        candidates, warnings = discover(roots, catalog, bool(args.root))
        output: dict[str, Any] = {
            "command": args.command, "read_only": True,
            "roots": [{"path": str(root), "exists": root.exists()} for root in roots],
            "catalog": str(absolute(args.catalog)), "warnings": warnings,
        }
        if catalog.get("warning"):
            output["warnings"].append({"path": str(args.catalog), "reason": catalog["warning"]})
        if args.command == "doctor":
            output.update(doctor(candidates, catalog, roots, bool(args.root)))
        else:
            selected = [item for item in candidates if matches_filters(item, args)]
            if args.command == "show":
                identifier = args.identifier.casefold()
                selected = [item for item in selected if identifier in {
                    value.casefold() for value in [item["id"], item["name"], *item["aliases"], *item["catalog_ids"]]
                }]
                output["ambiguous"] = len(selected) > 1
            elif args.command == "search":
                query = " ".join(args.query).strip()
                output["query"] = query
                if query:
                    ranked = []
                    for item in selected:
                        score, terms = search_score(item, query)
                        if score > 0:
                            ranked.append({**item, "retrieval_score": score, "matched_terms": terms})
                    selected = sorted(ranked, key=lambda item: (-item["retrieval_score"], item["name"], item["id"]))
                output["total_matches"] = len(selected)
                selected = selected[:args.limit]
            output["selection_status"] = "candidates_require_skill_read"
            output["candidates"] = selected
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc), "read_only": True}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
