#!/usr/bin/env python3
"""Run portable JSON/contract validation and every isolated unittest.

No third-party skills, drawing runtimes, AI APIs, or network are required.
Optionally check a full set of route_dry_run records with --records. This
verifies declared evidence constraints; scientific conditions and actual
rendering still require independent review and live execution.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from check_routes import check_records, read_json, validate_catalog, validate_suite
from skill_bundle import BundleError, load_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, help="Also check records covering every test-prompts.json case exactly once")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    errors = []
    documents = {}
    try:
        load_manifest(root / "references" / "skill-sources.json")
    except BundleError as exc:
        errors.append(f"references/skill-sources.json: {exc}")
    paths = []
    for directory, children, files in os.walk(root):
        children[:] = [name for name in children if name not in {
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            "local-reports", ".skill-bundle", ".skill-bundle-staging",
        }]
        paths.extend(Path(directory) / name for name in files if name.endswith(".json"))
    for path in sorted(paths):
        try:
            documents[path.relative_to(root).as_posix()] = read_json(path)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    for filename, validator in [("references/capabilities.json", validate_catalog), ("test-prompts.json", validate_suite)]:
        if filename not in documents:
            errors.append(f"{filename}: missing or unreadable")
        else:
            errors.extend(f"{filename}: {error}" for error in validator(documents[filename]))
    if args.records:
        try:
            result = check_records(documents.get("test-prompts.json"), read_json(args.records))
            errors.extend(f"route records: {error}" for error in result["errors"])
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"route records: {exc}")
    if errors:
        for error in errors:
            print("FAIL " + error, file=sys.stderr)
        return 1
    print(f"PASS {len(documents)} JSON documents and catalog/acceptance contracts", flush=True)
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(root / "tests"), "-p", "test_*.py", "-v"], cwd=root, check=False)
    if result.returncode:
        return result.returncode
    print("PASS portable verification; live skill/runtime and scientific figure validation are separate")
    if args.records:
        print("PASS declared route record constraints; free-text conditions still require independent review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
