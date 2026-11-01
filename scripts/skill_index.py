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
INTENTS = ("create", "edit", "choose", "palette", "qa", "diagram", "reconstruct", "reference", "maintenance")
LANGUAGE_FREE_INTENTS = {"palette", "qa", "reconstruct", "reference"}
DOMAIN_ALIASES = {"generic": "general", "clinical": "medical"}
INTENT_TAGS = {
    "create": {"new-plot", "known-chart"}, "edit": {"edit-code", "color-edit"},
    "choose": {"choose-chart"}, "palette": {"palette", "semantic-colors", "color-edit"},
    "qa": {"final-qa", "text-consistency", "image-processing"},
    "diagram": {"diagram", "workflow", "architecture", "path-diagram"},
    "reconstruct": {"editable-reconstruction", "image-to-ppt", "reference-reproduction", "match-image"},
    "reference": {"template-search", "style-reference", "visual-reference", "gallery"},
    "maintenance": {"skill-maintenance"},
}
CHINESE_TERMS = {
    "森林图": ("森林图", "forest"), "火山图": ("火山图", "volcano"),
    "散点图": ("散点", "scatter"), "箱线图": ("箱线", "boxplot"),
    "小提琴": ("小提琴", "violin"), "环形热图": ("环形热图", "circular-heatmap"),
    "热图": ("热图", "heatmap"), "中国地图": ("中国地图", "china", "map"),
    "地图": ("地图", "map"), "生存曲线": ("生存曲线", "survival", "kaplan-meier"),
    "流程图": ("流程图", "workflow", "diagram"), "机制": ("机制", "mechanism"),
    "配色": ("配色", "palette"), "色板": ("色板", "palette"),
    "色盲": ("色盲", "cvd"), "图例": ("图例", "legend"),
    "图注": ("图注", "caption"), "字体": ("字体", "font"),
    "导出": ("导出", "export"), "改图": ("改图", "edit"),
    "配对": ("配对", "paired"), "前后": ("前后", "paired"),
    "截图": ("截图", "image-to-ppt"), "可编辑": ("可编辑", "editable"),
    "基因": ("基因", "genetics"), "遗传": ("遗传", "genetics"),
    "临床": ("临床", "medical"), "组学": ("组学", "omics"),
}
GENERIC_CHART_TERMS = {
    "forest", "map", "heatmap", "scatter", "boxplot", "violin", "bar", "line", "plot", "chart", "figure",
    "volcano", "radar", "paired", "distribution", "diagram", "workflow", "edit", "create", "export",
    "new-plot", "known-chart", "edit-code", "multi-panel", "publication", "森林图", "热图", "地图",
}
STOP_WORDS = {"a", "an", "the", "to", "of", "and", "or", "for", "with", "in", "on", "my", "please", "use", "make", "draw", "i", "want", "how"}


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


def entry_source_state(path: Path, entry: dict[str, Any], digest: str, roots: list[Path], explicit_roots: bool) -> str:
    expected = {
        entry.get("source_hashes", {})[relative]
        for relative in entry.get("relative_paths", [])
        if relative in entry.get("source_hashes", {})
        and any(same_path(path, target) for target in catalog_targets({"relative_paths": [relative]}, roots, explicit_roots))
    }
    return "unchanged" if digest in expected else ("changed_since_review" if expected else "untracked")


def inspect_entry_points(path: Path, entry: dict[str, Any], contract_state: str) -> list[dict[str, Any]]:
    checked = []
    for point in entry.get("entry_points", []):
        relative = str(point.get("entry_path", ""))
        target = absolute(path.parent / relative)
        exists = bool(relative) and target.is_file()
        current = None
        read_error = None
        if exists:
            try:
                current = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError as exc:
                read_error = type(exc).__name__
        expected = point.get("source_sha256")
        state = "missing" if not exists else ("unreadable" if read_error else ("untracked" if not expected else ("unchanged" if expected == current else "changed_since_review")))
        checked.append({
            **point, "catalog_id": entry["id"], "path": str(target), "exists": exists,
            "current_sha256": current, "source_state": state,
            "contract_state": "reviewed_source" if contract_state == "unchanged" and state == "unchanged" else "historical_only",
            "runtime": "untested", **({"read_error": read_error} if read_error else {}),
        })
    return checked


def installation(path: Path, entries: list[dict[str, Any]], digest: str, roots: list[Path], explicit_roots: bool) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    entry_states = {entry["id"]: entry_source_state(path, entry, digest, roots, explicit_roots) for entry in entries}
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
    states = set(entry_states.values())
    source_state = "changed_since_review" if "changed_since_review" in states else ("untracked" if not states or "untracked" in states else "unchanged")
    registration = "unreviewed" if not entries else ("reviewed" if source_state == "unchanged" else "review_required")
    return {
        "skill_path": str(path), "catalog_ids": sorted(entry["id"] for entry in entries),
        "registration": registration, "source_state": source_state, "entry_source_states": entry_states,
        "entry_points": [point for entry in entries for point in inspect_entry_points(path, entry, entry_states[entry["id"]])],
        "resource_declarations": "reviewed_source" if source_state == "unchanged" else "historical_only",
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
        verified_ids = {identifier for item in group["installations"] for identifier, state in item["entry_source_states"].items() if state == "unchanged"}
        verified = [entry for entry in entries if entry["id"] in verified_ids]
        group["verified_entries"] = verified
        group["verified_catalog_ids"] = sorted(verified_ids)
        group["capability_state"] = "reviewed_source" if verified else "requires_source_read"
        group["catalog_entries_scope"] = "historical_inspection_only; verified_entries alone support capability filters"
        group["id"] = entries[0]["id"] if entries else "unreviewed-" + group["content_sha256"][:12]
        group["catalog_ids"] = [entry["id"] for entry in entries]
        registrations = {item["registration"] for item in group["installations"]}
        group["registration"] = "review_required" if "review_required" in registrations else ("reviewed" if "reviewed" in registrations else "unreviewed")
        source_states = {item["source_state"] for item in group["installations"]}
        group["source_state"] = "changed_since_review" if "changed_since_review" in source_states else ("unchanged" if "unchanged" in source_states else "untracked")
        group["runtime"] = "untested"
        group["skill_paths"] = sorted(item["skill_path"] for item in group["installations"])
        reviewed_paths = sorted(item["skill_path"] for item in group["installations"] if "unchanged" in item["entry_source_states"].values())
        group["reviewed_skill_paths"] = reviewed_paths
        group["skill_path"] = (reviewed_paths or group["skill_paths"])[0]
        group["read_first_options"] = group["skill_paths"]
        group["read_first_instruction"] = "Choose one installation; read its SKILL.md and required resources before deciding."
        group["directory_names"] = sorted(set(group["directory_names"]))
        group["historical_aliases"] = sorted({value for entry in entries for value in [entry.get("name", ""), *entry.get("aliases", [])] if value})
        group["aliases"] = sorted(set(group["aliases"] + group["directory_names"] + [
            value for entry in verified for value in [entry.get("name", ""), *entry.get("aliases", [])] if value
        ]))
        for field in ("domains", "task_tags", "outputs"):
            group[field] = sorted({value for entry in verified for value in entry.get(field, [])})
        group["domains"] = sorted({normalize_domain(value) for value in group["domains"]})
        group["backends"] = sorted({value for entry in verified for value in entry_backends(entry)})
        group["languages"] = group["backends"]
        group["intents"] = sorted({value for entry in verified for value in entry_intents(entry)})
        group["roles"] = sorted({entry["role"] for entry in verified if entry.get("role")})
        group["families"] = sorted({entry["family"] for entry in entries if entry.get("family")})
        group["entry_points"] = [point for item in group["installations"] for point in item["entry_points"]]
        candidates.append(group)
    return sorted(candidates, key=lambda item: (item["name"].casefold(), item["id"])), warnings


def list_value(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else ([] if value is None else [str(value)])


def normalize_domain(value: str) -> str:
    lowered = value.casefold()
    return DOMAIN_ALIASES.get(lowered, lowered)


def entry_backends(entry: dict[str, Any]) -> list[str]:
    # Containers are not drawing languages, including in legacy catalogs.
    return [value for value in entry.get("backends", entry.get("languages", [])) if value.casefold() not in {"svg", "pptx", "pdf", "png", "tiff"}]


def entry_intents(entry: dict[str, Any]) -> list[str]:
    if "intents" in entry:
        return list(entry["intents"])
    tags = {value.casefold() for value in entry.get("task_tags", [])}
    return [intent for intent, markers in INTENT_TAGS.items() if tags & markers or (intent == "maintenance" and entry.get("role") == "maintenance")]


def filter_scope(args: argparse.Namespace) -> dict[str, Any]:
    intent = args.intent
    inferred_from = None
    if intent is None and args.tag:
        inferred = {key for key in LANGUAGE_FREE_INTENTS if any(tag.casefold() in INTENT_TAGS[key] for tag in args.tag)}
        if len(inferred) == 1:
            intent = inferred.pop()
            inferred_from = "controlled_tag"
    exempt = intent in LANGUAGE_FREE_INTENTS
    return {
        "requested_language": args.language, "intent": intent, "intent_inferred_from": inferred_from,
        "effective_language": "any" if exempt else args.language,
        "language_scope": "source_language_not_applied_to_auxiliary_intent" if exempt else "drawing_source_backend",
        "explanation": "Language constrains source-code drawing; palette, qa, reconstruct and reference responsibilities use their own backends." if exempt else "Language applies to the drawing source backend; outputs such as SVG/PPTX are separate.",
    }


def has_filters(args: argparse.Namespace, scope: dict[str, Any]) -> bool:
    return bool(scope["effective_language"] != "any" or args.role or args.tag or args.domain or args.intent)


def assess_filters(candidate: dict[str, Any], args: argparse.Namespace, scope: dict[str, Any]) -> tuple[str, list[str]]:
    """Return match, unknown or mismatch without treating empty fields as facts."""
    if not has_filters(args, scope):
        return "match", []
    if not candidate["verified_entries"]:
        return "unknown", ["current_capability_card"]
    possible_unknowns: set[str] = set()
    for entry in candidate["verified_entries"]:
        unknown: set[str] = set()
        mismatch = False
        languages = {value.casefold() for value in entry_backends(entry)}
        language = scope["effective_language"]
        if language != "any":
            if not languages:
                unknown.add("language")
            elif language not in languages and "language-independent" not in languages:
                mismatch = True
        if args.role:
            if not entry.get("role"):
                unknown.add("role")
            elif entry["role"] != args.role:
                mismatch = True
        tags = {str(value).casefold() for value in entry.get("task_tags", [])}
        domains = {normalize_domain(value) for value in entry.get("domains", [])}
        intents = entry_intents(entry)
        for field, requested, available in (("tag", args.tag, tags), ("domain", args.domain, domains),
                                            ("intent", [args.intent] if args.intent else [], intents)):
            if requested:
                if not available:
                    unknown.add(field)
                elif any(value not in available for value in requested):
                    mismatch = True
        if not mismatch and not unknown:
            return "match", []
        if not mismatch:
            possible_unknowns.update(unknown)
    return ("unknown", sorted(possible_unknowns)) if possible_unknowns else ("mismatch", [])


def vocabulary(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "domains": sorted({normalize_domain(value) for entry in catalog["entries"] for value in entry.get("domains", [])}),
        "tags": sorted({value.casefold() for entry in catalog["entries"] for value in entry.get("task_tags", [])}),
        "intents": list(INTENTS), "roles": ["primary", "helper", "reference", "maintenance"],
        "languages": ["r", "python", "matlab", "any"], "domain_aliases": DOMAIN_ALIASES,
        "scope": "catalog vocabulary; availability and compatibility require current source review",
    }


def query_terms(query: str, catalog: dict[str, Any]) -> list[str]:
    lowered = query.casefold()
    terms = {term for term in re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", lowered) if term not in STOP_WORDS}
    for phrase, expanded in CHINESE_TERMS.items():
        if phrase in lowered:
            terms.update(expanded)
    # Curated local tags supplement the small phrase list, without loading bodies.
    for entry in catalog["entries"]:
        for tag in entry.get("task_tags", []):
            if re.search(r"[\u3400-\u9fff]", tag) and len(tag) >= 2 and tag.casefold() in lowered:
                terms.add(tag.casefold())
    for phrase in re.findall(r"[\u3400-\u9fff]+", lowered):
        if len(phrase) <= 12:
            terms.add(phrase)
    terms.update(DOMAIN_ALIASES[term] for term in list(terms) if term in DOMAIN_ALIASES)
    return sorted(terms)


def term_match(term: str, value: str) -> str | None:
    lowered = value.casefold()
    if re.search(r"[\u3400-\u9fff]", term):
        return "phrase" if term in lowered else None
    if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", lowered):
        return "whole_word"
    return "substring" if len(term) >= 3 and term in lowered else None


def search_score(candidate: dict[str, Any], terms: list[str]) -> tuple[int, list[str], list[dict[str, Any]]]:
    fields = [("name", candidate["name"], 8), ("aliases", " ".join(candidate["aliases"]), 8),
              ("catalog_id", " ".join(candidate["verified_catalog_ids"]), 8), ("description", candidate["description"], 3)]
    for entry in candidate["verified_entries"]:
        for key, weight in (("domains", 5), ("task_tags", 6), ("when", 2)):
            fields.append((key, " ".join(list_value(entry.get(key))), weight))
    matched: set[str] = set()
    score = 0
    evidence = []
    for field, value, weight in fields:
        for term in terms:
            kind = term_match(term, value)
            if kind is None:
                continue
            contribution = 1 if kind == "substring" else weight
            score += contribution
            matched.add(term)
            start = max(value.casefold().find(term) - 45, 0)
            evidence.append({"field": field, "term": term, "match": kind, "weight": contribution, "excerpt": value[start:start + 150]})
    # A stale card's exact id remains navigable, but its constituent words do
    # not become current capability evidence.
    for identifier in set(candidate["catalog_ids"]) - set(candidate["verified_catalog_ids"]):
        if identifier.casefold() in terms:
            score += 8
            matched.add(identifier.casefold())
            evidence.append({"field": "historical_identity", "term": identifier.casefold(),
                             "match": "exact_identity", "weight": 8, "excerpt": identifier})
    return score, sorted(matched), evidence


def domain_rank(candidate: dict[str, Any], terms: list[str], args: argparse.Namespace, known_domains: list[str]) -> tuple[int, str]:
    """Prefer domain evidence over generic chart overlap; this is no semantic judge."""
    domains = set(candidate["domains"])
    if not domains:
        return 1, "domain_unreviewed"
    requested = set(args.domain) | {normalize_domain(term) for term in terms if normalize_domain(term) in known_domains}
    if domains & requested:
        return 0, "explicit_domain_evidence"
    identity = {candidate["name"].casefold(), *[value.casefold() for value in candidate["catalog_ids"]]}
    distinctive = {tag.casefold() for tag in candidate["task_tags"] if tag.casefold() not in GENERIC_CHART_TERMS}
    supported = bool(identity & set(terms)) or any(term not in GENERIC_CHART_TERMS and term in distinctive for term in terms)
    if supported:
        return 0, "specific_skill_or_task_evidence"
    if "general" in domains:
        return 1 if requested else 0, "general_capability"
    return 2, "specialized_domain_without_query_evidence"


def summarize(candidate: dict[str, Any], details: bool) -> dict[str, Any]:
    if details:
        return {key: value for key, value in candidate.items() if key != "verified_entries"}
    keys = ("id", "name", "description", "skill_path", "registration", "source_state", "capability_state", "filter_status", "unknown_filter_fields", "roles", "backends", "languages", "domains", "intents", "outputs", "runtime", "retrieval_score", "matched_terms", "domain_evidence", "review_reason")
    result = {key: candidate[key] for key in keys if key in candidate}
    result["description"] = candidate["description"][:280]
    result["installation_count"] = len(candidate["installations"])
    result["entry_point_count"] = len(candidate["entry_points"])
    result["resource_states"] = sorted({item["resource_state"] for item in candidate["installations"]})
    if "evidence" in candidate:
        result["evidence"] = candidate["evidence"][:4]
        result["evidence_total"] = len(candidate["evidence"])
    result["details_hint"] = "show " + candidate["id"]
    return result


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
        "entry_point_issues": [
            {"id": candidate["id"], **point} for candidate in candidates for point in candidate["entry_points"]
            if point["source_state"] != "unchanged" or point["contract_state"] != "reviewed_source"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    def add_options(target: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
        def default(value: Any) -> Any:
            return argparse.SUPPRESS if suppress_defaults else value

        target.add_argument("--root", action="append", default=default([]), help="Scan only these roots; repeatable")
        target.add_argument("--catalog", type=Path, default=default(Path(__file__).resolve().parent.parent / "references" / "capabilities.json"))
        target.add_argument("--limit", type=int, default=default(5), help="Maximum search candidates (default: 5)")
        target.add_argument("--review-limit", type=int, default=default(3), help="Maximum unverified review candidates (default: 3)")
        target.add_argument("--details", action="store_true", default=default(False), help="Expand search/list results; show is always detailed")
        target.add_argument("--language", type=str.lower, choices=["r", "python", "matlab", "any"], default=default("any"))
        target.add_argument("--intent", choices=INTENTS, default=default(None))
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
    words = commands.add_parser("vocabulary", help="List controlled domains, tags, intents and aliases")
    for command_parser in (listing, search, show, checking, words):
        add_options(command_parser, suppress_defaults=True)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.review_limit < 0:
        parser.error("--review-limit must not be negative")
    normalizations = [
        {"filter": field, "requested": value, "applied": normalize(value)}
        for field, values, normalize in (("domain", args.domain, normalize_domain), ("tag", args.tag, str.casefold))
        for value in values if value != normalize(value)
    ]
    args.domain = [normalize_domain(value) for value in args.domain]
    args.tag = [value.casefold() for value in args.tag]
    roots = list(dict.fromkeys(absolute(Path(path)) for path in args.root)) if args.root else default_roots()
    try:
        catalog = load_catalog(absolute(args.catalog))
        words = vocabulary(catalog)
        output: dict[str, Any] = {
            "schema_version": 2, "command": args.command, "read_only": True,
            "roots": [{"path": str(root), "exists": root.exists()} for root in roots],
            "catalog": str(absolute(args.catalog)), "warnings": [],
            "filter_normalizations": normalizations,
        }
        if catalog.get("warning"):
            output["warnings"].append({"path": str(args.catalog), "reason": catalog["warning"]})
        if args.command == "vocabulary":
            output.update(words)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        diagnostics = [
            {"filter": field, "unknown_values": [value for value in requested if value not in available], "available_values": available}
            for field, requested, available in (("domain", args.domain, words["domains"]), ("tag", args.tag, words["tags"]))
            if any(value not in available for value in requested)
        ]
        if diagnostics:
            output.update({"error": "unknown_filter_value", "diagnostics": diagnostics, "vocabulary_hint": "vocabulary"})
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 2
        candidates, warnings = discover(roots, catalog, bool(args.root))
        output["warnings"].extend(warnings)
        if args.command == "doctor":
            output.update(doctor(candidates, catalog, roots, bool(args.root)))
        else:
            scope = filter_scope(args)
            output["filter_scope"] = scope
            selected = []
            review = []
            pending_without_query = 0
            filtering = has_filters(args, scope)
            if args.command == "show":
                identifier = args.identifier.casefold()
                selected = [item for item in candidates if identifier in {
                    value.casefold() for value in [item["id"], item["name"], *item["aliases"], *item["catalog_ids"], *item["historical_aliases"]]
                }]
                output["ambiguous"] = len(selected) > 1
            else:
                query = " ".join(args.query).strip() if args.command == "search" else ""
                output["query"] = query
                terms = query_terms(query, catalog)
                output["query_terms"] = terms
                output["score_scope"] = "lexical evidence weights; not correctness probability or permission to execute"
                for candidate in candidates:
                    item = dict(candidate)
                    if query:
                        score, matched, evidence = search_score(item, terms)
                        if score <= 0:
                            continue
                        rank, reason = domain_rank(item, terms, args, words["domains"])
                        item.update({"retrieval_score": score, "matched_terms": matched, "evidence": evidence, "domain_rank": rank, "domain_evidence": reason})
                    assessment, unknown_fields = assess_filters(item, args, scope)
                    if assessment == "match":
                        item["filter_status"] = "reviewed_filters_match" if filtering else "not_filtered"
                        selected.append(item)
                    elif assessment == "unknown":
                        if query:
                            item.update({"filter_status": "requires_source_read_not_compatible", "unknown_filter_fields": unknown_fields,
                                         "review_reason": "Current source has query evidence, but a current capability card or required filter field is unverified."})
                            review.append(item)
                        else:
                            pending_without_query += 1
                if query:
                    sort_key = lambda item: (item["domain_rank"], -item["retrieval_score"], item["name"], item["id"])
                    selected.sort(key=sort_key)
                    review.sort(key=sort_key)
                output["total_matches"] = len(selected)
                output["total_review_matches"] = len(review)
                output["review_pending_without_query"] = pending_without_query
                if pending_without_query:
                    output["review_hint"] = "Add query keywords to retrieve relevant unverified candidates; pending count is not a relevance or compatibility claim."
                if args.command == "search":
                    selected = selected[:args.limit]
                review = review[:args.review_limit]
            for item in selected:
                if args.command == "show":
                    assessment, unknown_fields = assess_filters(item, args, scope)
                    item["filter_status"] = "not_filtered" if not filtering else {"match": "reviewed_filters_match", "unknown": "requires_source_read_not_compatible", "mismatch": "known_filter_mismatch"}[assessment]
                    if unknown_fields:
                        item["unknown_filter_fields"] = unknown_fields
            output["selection_status"] = "candidates_require_skill_read"
            output["candidates"] = [summarize(item, args.details or args.command == "show") for item in selected]
            output["review_candidates"] = [summarize(item, args.details) for item in review]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"schema_version": 2, "error": type(exc).__name__, "message": str(exc), "read_only": True}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
