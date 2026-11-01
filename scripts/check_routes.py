#!/usr/bin/env python3
"""Validate declared route evidence, not scientific correctness or rendering.

Records are a JSON array or {"records": [...]}, covering every prompt exactly
once. A pass checks explicit fields only; free-text conditions always require
independent review. Files/entry points are evidence references, not opened by
this checker. It needs no installed drawing skills, backend, API, or network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

ALLOWED_ACTIONS = frozenset({
    "search_candidates", "read_skill", "inspect_entry", "inspect_existing_code",
    "choose_chart", "plan_plot", "plan_edit", "select_palette",
    "inspect_output_requirements", "inspect_resources", "inspect_figure",
    "plan_fallback", "preserve_results", "preserve_language", "report_missing_input",
})
FORBIDDEN_UPSTREAM_ACTIONS = frozenset({
    "rerun_upstream_analysis", "refit_model", "train_model", "recompute_statistics",
    "run_gwas", "run_magma", "run_ldsc", "rerun_differential_expression",
    "render_figure", "execute_backend",
})
RECORD_FIELDS = frozenset({
    "case_id", "execution_target", "primary_skill", "helpers", "language",
    "read_files", "entry_point", "actions", "verification_level",
})
ENTRY_FIELDS = frozenset({
    "id", "entry_path", "backend", "input_kind", "required_inputs",
    "analysis_effect", "source_kind", "outputs", "constraints",
})
LANGUAGES = {"r": "r", "python": "python", "matlab": "matlab", "any": "any"}
MODES = {"create", "edit", "choose", "style", "qa", "diagram", "reference"}
OUTPUT_CONTAINERS = {"svg", "pdf", "pptx", "png", "jpg", "jpeg", "tif", "tiff"}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def strings(value: Any, *, allow_empty: bool = True) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(nonempty(item) for item in value)


def language(value: Any) -> str | None:
    return LANGUAGES.get(value.strip().casefold()) if isinstance(value, str) else None


def read_json(path: Path) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"non-JSON numeric constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)


def validate_suite(suite: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list) or not suite["cases"]:
        return ["prompts must be an object with a nonempty cases array"]
    seen = set()
    for position, case in enumerate(suite["cases"]):
        label = f"cases[{position}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected object")
            continue
        identifier = case.get("id")
        if not nonempty(identifier):
            errors.append(f"{label}: id must be a nonempty string")
        elif identifier in seen:
            errors.append(f"{label}: duplicate case id {identifier}")
        else:
            seen.add(identifier)
        if not nonempty(case.get("prompt")):
            errors.append(f"{label}: prompt must be a nonempty string")
        task = case.get("task_spec")
        if not isinstance(task, dict):
            errors.append(f"{label}: task_spec must be an object")
        else:
            if not isinstance(task.get("mode"), str) or task["mode"] not in MODES:
                errors.append(f"{label}: unsupported task_spec.mode")
            if language(task.get("language")) is None:
                errors.append(f"{label}: language must be R, python, matlab, or any")
            if not nonempty(task.get("domain")):
                errors.append(f"{label}: domain must be a nonempty string")
            if "explicit_skill" in task and not nonempty(task["explicit_skill"]):
                errors.append(f"{label}: explicit_skill must be a nonempty string")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{label}: expected must be an object")
            continue
        for field in ("primary_any_of", "must_not_primary", "conditions"):
            if not strings(expected.get(field), allow_empty=field != "primary_any_of"):
                errors.append(f"{label}: expected.{field} must be a string array" + (" with at least one item" if field == "primary_any_of" else ""))
        if strings(expected.get("primary_any_of")) and strings(expected.get("must_not_primary")):
            overlap = set(expected["primary_any_of"]) & set(expected["must_not_primary"])
            if overlap:
                errors.append(f"{label}: allowed/forbidden primary overlap: {sorted(overlap)}")
        for field in ("allow_existing_code", "allow_explicit_fallback"):
            if field in expected and not isinstance(expected[field], bool):
                errors.append(f"{label}: expected.{field} must be boolean")
        if "forbidden_actions" in expected and not strings(expected["forbidden_actions"]):
            errors.append(f"{label}: forbidden_actions must be a string array")
        if expected.get("allow_existing_code") and isinstance(task, dict) and task.get("mode") != "edit":
            errors.append(f"{label}: allow_existing_code requires edit mode")
        if expected.get("allow_explicit_fallback") and (not isinstance(task, dict) or not nonempty(task.get("explicit_skill"))):
            errors.append(f"{label}: allow_explicit_fallback needs an explicit_skill")
    return errors


def validate_catalog(catalog: Any) -> list[str]:
    """Validate portable metadata shape; deliberately do not probe local paths."""
    if not isinstance(catalog, dict) or not isinstance(catalog.get("entries"), list):
        return ["catalog must be an object with an entries array"]
    errors: list[str] = []
    seen = set()
    for position, entry in enumerate(catalog["entries"]):
        label = f"entries[{position}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected object")
            continue
        identifier = entry.get("id")
        if not nonempty(identifier):
            errors.append(f"{label}: missing id")
        elif identifier in seen:
            errors.append(f"{label}: duplicate id {identifier}")
        else:
            seen.add(identifier)
        if not strings(entry.get("relative_paths"), allow_empty=False):
            errors.append(f"{label}: relative_paths must be a nonempty string array")
        hashes = entry.get("source_hashes", {})
        if not isinstance(hashes, dict) or any(not nonempty(key) or not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value) for key, value in hashes.items()):
            errors.append(f"{label}: source_hashes must map paths to hexadecimal SHA-256 digests")
        for field in ("languages", "backends", "outputs", "intents"):
            if field in entry and not strings(entry[field]):
                errors.append(f"{label}: {field} must be a string array")
        for field in ("languages", "backends"):
            if strings(entry.get(field)) and any(value.casefold() in OUTPUT_CONTAINERS for value in entry[field]):
                errors.append(f"{label}: {field} contains an output container instead of a backend")
        points = entry.get("entry_points", [])
        if not isinstance(points, list):
            errors.append(f"{label}: entry_points must be an array")
            continue
        point_ids = set()
        for number, point in enumerate(points):
            where = f"{label}.entry_points[{number}]"
            if not isinstance(point, dict):
                errors.append(f"{where}: expected object")
                continue
            missing = ENTRY_FIELDS - point.keys()
            if missing:
                errors.append(f"{where}: missing fields {sorted(missing)}")
            for field in ("id", "entry_path", "backend", "input_kind", "source_kind"):
                if not nonempty(point.get(field)):
                    errors.append(f"{where}: {field} must be a nonempty string")
            if nonempty(point.get("id")):
                if point["id"] in point_ids:
                    errors.append(f"{where}: duplicate entry id {point['id']}")
                point_ids.add(point["id"])
            for field in ("required_inputs", "outputs", "constraints"):
                if not strings(point.get(field)):
                    errors.append(f"{where}: {field} must be a string array")
            if not isinstance(point.get("analysis_effect"), str) or point["analysis_effect"] not in {"none", "refit_or_test", "unknown"}:
                errors.append(f"{where}: analysis_effect must be none, refit_or_test, or unknown")
            if nonempty(point.get("backend")) and point["backend"].casefold() in OUTPUT_CONTAINERS:
                errors.append(f"{where}: backend must not be an output container")
            if "source_sha256" in point and (not isinstance(point["source_sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", point["source_sha256"])):
                errors.append(f"{where}: source_sha256 must be a 64-character hexadecimal digest")
    return errors


def check_records(suite: Any, document: Any) -> dict[str, Any]:
    errors = validate_suite(suite)
    cases = {case["id"]: case for case in suite.get("cases", []) if isinstance(case, dict) and nonempty(case.get("id"))} if isinstance(suite, dict) and isinstance(suite.get("cases"), list) else {}
    records = document.get("records") if isinstance(document, dict) else document
    if not isinstance(records, list) or not records:
        errors.append("records must be a nonempty JSON array or an object with a nonempty records array")
        records = []
    seen = set()
    results = []
    for position, record in enumerate(records):
        label = f"records[{position}]"
        local: list[str] = []
        if not isinstance(record, dict):
            errors.append(f"{label}: expected object")
            continue
        missing = RECORD_FIELDS - record.keys()
        if missing:
            local.append(f"missing fields {sorted(missing)}")
        identifier = record.get("case_id")
        if not nonempty(identifier):
            local.append("case_id must be a nonempty string")
        elif identifier in seen:
            local.append(f"duplicate case record {identifier}")
        else:
            seen.add(identifier)
        case = cases.get(identifier) if isinstance(identifier, str) else None
        if case is None:
            local.append("unknown case_id")
        if record.get("verification_level") != "route_dry_run":
            local.append("verification_level must be route_dry_run; this checker cannot certify rendering")
        for field in ("helpers", "actions"):
            if not strings(record.get(field), allow_empty=field != "actions"):
                local.append(f"{field} must be a string array" + (" with at least one action" if field == "actions" else ""))
        if strings(record.get("helpers")) and len(set(record["helpers"])) != len(record["helpers"]):
            local.append("helpers must not contain duplicates")
        if not strings(record.get("read_files"), allow_empty=False):
            local.append("read_files must be a nonempty string array of evidence references")
        if "entry_point" in record and record["entry_point"] is not None and not nonempty(record["entry_point"]):
            local.append("entry_point must be null or a nonempty string")
        actual_language = language(record.get("language"))
        if actual_language is None:
            local.append("language must be R, python, matlab, or any")
        actions = record.get("actions") if strings(record.get("actions")) else []
        prohibited = set(actions) & FORBIDDEN_UPSTREAM_ACTIONS
        if prohibited:
            local.append(f"forbidden upstream/execution actions: {sorted(prohibited)}")
        unknown_actions = set(actions) - ALLOWED_ACTIONS - FORBIDDEN_UPSTREAM_ACTIONS
        if unknown_actions:
            local.append(f"unknown actions (use documented tokens): {sorted(unknown_actions)}")
        if case is not None and not validate_suite({"cases": [case]}):
            expected, task = case["expected"], case["task_spec"]
            primary, target = record.get("primary_skill"), record.get("execution_target")
            if target == "existing_code":
                if expected.get("allow_existing_code") is not True:
                    local.append("existing_code execution was not permitted by this case")
                if primary is not None:
                    local.append("existing_code requires primary_skill=null")
            elif target == "skill":
                if not nonempty(primary):
                    local.append("skill execution requires a nonempty primary_skill")
                elif primary not in expected["primary_any_of"]:
                    local.append("primary_skill is not in primary_any_of")
            else:
                local.append("execution_target must be skill or existing_code")
            if isinstance(primary, str) and primary in expected["must_not_primary"]:
                local.append("primary_skill is forbidden by must_not_primary")
            if isinstance(primary, str) and strings(record.get("helpers")) and primary in record["helpers"]:
                local.append("primary_skill must not also be listed as a helper")
            if language(task["language"]) != "any" and actual_language != language(task["language"]):
                local.append(f"hard language constraint violated: expected {task['language']}")
            explicit = task.get("explicit_skill")
            if explicit and (primary != explicit or target != "skill"):
                if expected.get("allow_explicit_fallback") is not True:
                    local.append(f"explicit_skill must be preserved: {explicit}")
                else:
                    if not nonempty(record.get("notes")):
                        local.append("authorized explicit fallback requires nonempty notes; rationale needs independent review")
                    evidence_files = record.get("read_files") if strings(record.get("read_files")) else []
                    if not any(explicit in Path(path).parts for path in evidence_files):
                        local.append("explicit fallback must reference reading the explicitly requested skill")
            forbidden = set(expected.get("forbidden_actions", [])) & set(actions)
            if forbidden:
                local.append(f"actions forbidden by this case: {sorted(forbidden)}")
            conditions = expected["conditions"]
        else:
            conditions = []
        errors.extend(f"{label} ({identifier}): {item}" for item in local)
        results.append({"case_id": identifier, "mechanical_checks": "fail" if local else "pass", "independent_review_required": conditions})
    missing_cases = sorted(set(cases) - seen)
    if missing_cases:
        errors.append(f"missing case records: {missing_cases}")
    return {
        "mechanical_checks": "fail" if errors else "pass",
        "record_count": len(records), "expected_case_count": len(cases),
        "verification_level": "route_dry_run", "rendering_verified": False,
        "evidence_files_checked_for_existence": False,
        "free_text_conditions_automatically_verified": False,
        "errors": errors, "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog="Actions: " + ", ".join(sorted(ALLOWED_ACTIONS)))
    parser.add_argument("--prompts", type=Path, default=Path(__file__).resolve().parent.parent / "test-prompts.json", help="Acceptance prompt JSON; every case must have exactly one record")
    parser.add_argument("--records", type=Path, required=True, help="Nonempty route record array, or {records: [...]} JSON; read_files is required, entry_point may be null")
    args = parser.parse_args(argv)
    try:
        result = check_records(read_json(args.prompts), read_json(args.records))
    except (OSError, ValueError, TypeError) as exc:
        result = {"mechanical_checks": "fail", "rendering_verified": False, "errors": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["mechanical_checks"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
