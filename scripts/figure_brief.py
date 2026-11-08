#!/usr/bin/env python3
"""Validate a versioned FigureBrief and list GWAS figure recipes.

The validator describes *what a figure may display*.  It never reads or
recomputes GWAS statistics, executes renderer code, or changes thresholds.
Paths in ``input_records`` are provenance labels; use ``--check-paths`` only
when validating a project-local brief whose files should already exist.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


SCHEMA = "figure-brief.v1"
LANGUAGES = {"R", "Python", "any"}
DATA_STATES = {"accepted-results", "derived-results", "raw-observations"}
PANEL_ROLES = {"main", "supplement", "exploratory"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
MAX_TEXT = 8192


class BriefError(ValueError):
    """A structural or provenance-contract error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BriefError(message)


def read_json(path: Path):
    require(path.is_file(), f"missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BriefError(f"invalid JSON: {path}: {exc}") from exc


def text(value, label: str, *, allow_empty: bool = False) -> str:
    require(isinstance(value, str), f"{label} must be text")
    require("\x00" not in value and len(value) <= MAX_TEXT, f"{label} contains invalid or oversized text")
    if not allow_empty:
        require(bool(value.strip()), f"{label} must be non-empty")
    return value


def obj(value, label: str, *, nonempty: bool = False) -> dict:
    require(isinstance(value, dict), f"{label} must be an object")
    require(not nonempty or bool(value), f"{label} must be non-empty")
    return value


def array(value, label: str, *, nonempty: bool = False) -> list:
    require(isinstance(value, list), f"{label} must be an array")
    require(not nonempty or bool(value), f"{label} must be non-empty")
    return value


def identifier(value, label: str) -> str:
    text(value, label)
    require(SAFE_ID.fullmatch(value) is not None, f"{label} has unsafe id: {value!r}")
    return value


def path_label(value, label: str) -> str:
    value = text(value, label)
    require(not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value), f"{label} must be a local provenance path")
    require("\\" not in value and "\x00" not in value, f"{label} contains unsafe path characters")
    return value


def validate_input_records(values: list, *, check_paths: bool, base: Path) -> list[str]:
    require(1 <= len(values) <= 200, "input_records must contain 1–200 records")
    ids = set()
    messages = []
    for index, item in enumerate(values):
        label = f"input_records[{index}]"
        item = obj(item, label)
        ident = identifier(item.get("id"), f"{label}.id")
        require(ident not in ids, f"duplicate input record id: {ident}")
        ids.add(ident)
        path = path_label(item.get("path"), f"{label}.path")
        text(item.get("role"), f"{label}.role")
        if check_paths:
            target = Path(path).expanduser()
            if not target.is_absolute():
                target = base / target
            require(target.is_file(), f"input record does not exist: {target}")
    return messages


def validate_candidate_figures(values: list) -> None:
    require(1 <= len(values) <= 100, "candidate_figures must contain 1–100 entries")
    ids = set()
    for index, item in enumerate(values):
        label = f"candidate_figures[{index}]"
        item = obj(item, label)
        ident = identifier(item.get("id"), f"{label}.id")
        require(ident not in ids, f"duplicate candidate figure id: {ident}")
        ids.add(ident)
        text(item.get("form"), f"{label}.form")
        require(item.get("panel_role") in PANEL_ROLES, f"{label}.panel_role must be one of {sorted(PANEL_ROLES)}")
        text(item.get("primary_skill"), f"{label}.primary_skill")
        helpers = array(item.get("helpers", []), f"{label}.helpers")
        for helper_index, helper in enumerate(helpers):
            text(helper, f"{label}.helpers[{helper_index}]")
        text(item.get("scientific_purpose"), f"{label}.scientific_purpose")
        for key in ("allowed_style_variants", "forbidden_shortcuts"):
            values_for_key = array(item.get(key), f"{label}.{key}", nonempty=True)
            for value_index, value in enumerate(values_for_key):
                text(value, f"{label}.{key}[{value_index}]")


def validate_brief(value: dict, *, base: Path | None = None, check_paths: bool = False) -> dict:
    value = obj(value, "FigureBrief", nonempty=True)
    require(value.get("schema_version") == SCHEMA, f"schema_version must be {SCHEMA}")
    for key in ("project", "study_question", "population"):
        text(value.get(key), key)
    require(value.get("data_status") in DATA_STATES, f"data_status must be one of {sorted(DATA_STATES)}")
    require(value.get("language_preference") in LANGUAGES,
            f"language_preference must be one of {sorted(LANGUAGES)}")
    path_base = base or Path.cwd()
    if "project_root" in value:
        root_label = path_label(value.get("project_root"), "project_root")
        project_root = Path(root_label).expanduser()
        if not project_root.is_absolute():
            project_root = path_base / project_root
        project_root = project_root.resolve()
        if check_paths:
            require(project_root.is_dir(), f"project_root does not exist: {project_root}")
        path_base = project_root
    obj(value.get("scientific_contract"), "scientific_contract", nonempty=True)
    validate_input_records(array(value.get("input_records"), "input_records", nonempty=True),
                           check_paths=check_paths, base=path_base)
    validate_candidate_figures(array(value.get("candidate_figures"), "candidate_figures", nonempty=True))

    output = obj(value.get("output_contract"), "output_contract", nonempty=True)
    required_outputs = array(output.get("required"), "output_contract.required", nonempty=True)
    require(all(isinstance(item, str) and item.strip() for item in required_outputs),
            "output_contract.required must contain non-empty strings")
    for key in ("vector_first", "reference_images_are_style_only", "human_selection_required_before_production"):
        require(isinstance(output.get(key), bool), f"output_contract.{key} must be boolean")

    policy = obj(value.get("evolution_policy"), "evolution_policy", nonempty=True)
    require(policy.get("mode") == "bounded-human-in-the-loop",
            "evolution_policy.mode must be bounded-human-in-the-loop")
    memory = array(policy.get("append_only_memory"), "evolution_policy.append_only_memory", nonempty=True)
    require(all(isinstance(item, str) and item.strip() for item in memory),
            "evolution_policy.append_only_memory must contain strings")
    for key in ("automatic_skill_self_edit", "automatic_github_push"):
        require(policy.get(key) is False, f"{key} must remain false in a FigureBrief")
    for key in ("reference_images_are_style_only", "human_confirmation_required"):
        if key in policy:
            require(policy.get(key) is True, f"evolution_policy.{key} must remain true")
    if "memory_schema" in policy:
        identifier(policy.get("memory_schema"), "evolution_policy.memory_schema")
    if "promotion_policy" in policy:
        text(policy.get("promotion_policy"), "evolution_policy.promotion_policy")
    text(policy.get("promotion_gate"), "evolution_policy.promotion_gate")
    return {"ok": True, "schema_version": SCHEMA, "candidate_count": len(value["candidate_figures"]),
            "input_count": len(value["input_records"]), "data_status": value["data_status"],
            "path_base": str(path_base) if "project_root" in value else None}


def load_recipes(path: Path) -> dict:
    value = read_json(path)
    obj(value, "recipe catalog", nonempty=True)
    require(value.get("schema_version") == "gwas-figure-recipes.v1", "unsupported recipe catalog schema")
    recipes = obj(value.get("recipes"), "recipe catalog.recipes", nonempty=True)
    for recipe_id, recipe in recipes.items():
        identifier(recipe_id, "recipe id")
        recipe = obj(recipe, f"recipe {recipe_id}", nonempty=True)
        text(recipe.get("title"), f"recipe {recipe_id}.title")
        require(recipe.get("analysis_effect") == "none", f"recipe {recipe_id} cannot refit upstream analyses")
        require(recipe.get("backend") in {"R", "Python", "any"}, f"recipe {recipe_id}.backend is invalid")
        required = array(recipe.get("required_columns"), f"recipe {recipe_id}.required_columns", nonempty=True)
        require(all(isinstance(item, str) and item.strip() for item in required),
                f"recipe {recipe_id}.required_columns must contain strings")
        constraints = array(recipe.get("evidence_boundaries"), f"recipe {recipe_id}.evidence_boundaries", nonempty=True)
        require(all(isinstance(item, str) and item.strip() for item in constraints),
                f"recipe {recipe_id}.evidence_boundaries must contain strings")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a FigureBrief")
    validate.add_argument("--brief", required=True, type=Path)
    validate.add_argument("--check-paths", action="store_true", help="also require input_records paths to exist")
    validate.add_argument("--json", action="store_true", help="print a JSON summary")
    recipes = commands.add_parser("list-recipes", help="list validated GWAS figure recipes")
    recipes.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parent.parent / "references" / "gwas-figure-recipes.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            brief = args.brief.resolve(strict=True)
            result = validate_brief(read_json(brief), base=brief.parent, check_paths=args.check_paths)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
                  f"PASS FigureBrief {brief} ({result['candidate_count']} candidates, {result['input_count']} inputs)")
        else:
            catalog = load_recipes(args.catalog.resolve(strict=True))
            for recipe_id, recipe in catalog["recipes"].items():
                print(f"{recipe_id}\t{recipe['backend']}\t{recipe['title']}")
        return 0
    except (OSError, ValueError, TypeError, KeyError, BriefError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"FAIL {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
