#!/usr/bin/env python3
"""Audit an accepted cluster-by-trait display contract; never fit or filter models.

Uses only the Python standard library. A PASS concerns the membership mapping,
not the correctness of HyPrColoc, the scientific conclusion or the rendered art.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def table(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        fields = reader.fieldnames or []
        require(len(fields) == len(set(fields)), f"duplicate column names: {path}")
        require(set(required) <= set(fields), f"missing columns in {path}: {sorted(set(required) - set(fields))}")
        rows = list(reader)
    require(bool(rows), f"empty table: {path}")
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
            f"malformed TSV row: {path}")
    return rows


def boolean(value):
    values = {"true": True, "false": False, "1": True, "0": False}
    require(isinstance(value, str) and value.lower() in values, f"invalid boolean: {value!r}")
    return values[value.lower()]


def probability(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} is not numeric") from exc
    require(math.isfinite(result) and 0 <= result <= 1, f"{label} must be finite within [0, 1]")
    return result


def audit(clusters, memberships, *, threshold, rendered=None, connectors=None, trait_order=None, source_traits=None):
    """Check exact row identity, states and optional displayed incidence/segments."""
    require(bool(clusters) and bool(memberships), "clusters and memberships must not be empty")
    threshold = probability(threshold, "PP threshold")
    rows, expected = {}, set()
    for row in clusters:
        key = row["cluster_id"]
        require(bool(key.strip()) and key not in rows, f"empty/duplicate cluster_id: {key!r}")
        require(bool(row["window_id"].strip()) and bool(row["candidate_snp"].strip()),
                f"{key}: region/window and candidate SNP must be recorded")
        traits = row["trait_set"].split("|")
        require(all(t.strip() == t and t for t in traits) and len(traits) >= 2 and len(set(traits)) == len(traits),
                f"{key}: trait_set must contain at least two distinct, non-empty pipe-separated traits")
        pp = probability(row["cluster_pp"], f"{key}.cluster_pp")
        require(pp > threshold, f"{key}: PP does not satisfy declared strict > threshold; do not silently filter")
        snp_fraction = row.get("candidate_snp_posterior_fraction", "")
        if snp_fraction not in {"", "NA"}:
            probability(snp_fraction, f"{key}.candidate_snp_posterior_fraction")
        rows[key] = dict(candidate_snp=row["candidate_snp"], window_id=row["window_id"],
                         cluster_pp=pp, traits=traits, member_count=len(traits),
                         candidate_snp_posterior_fraction=snp_fraction or None)
        expected.update((key, trait) for trait in traits)

    cells, observed, all_traits = {}, set(), set()
    for cell in memberships:
        key, trait = cell["cluster_id"], cell["trait"]
        require(key in rows and bool(trait.strip()) and trait.strip() == trait, f"unknown row or invalid trait: {key!r}, {trait!r}")
        require((key, trait) not in cells, f"duplicate membership cell: {key}, {trait}")
        in_input, in_cluster = boolean(cell["in_input"]), boolean(cell["in_cluster"])
        require(not in_cluster or in_input, f"{key}/{trait}: a member cannot be outside the regional input")
        cells[key, trait] = in_input, in_cluster
        all_traits.add(trait)
        if in_cluster:
            observed.add((key, trait))
    require(observed == expected, f"source member set mismatch: missing={sorted(expected-observed)}, extra={sorted(observed-expected)}")
    if source_traits is not None:
        require(bool(source_traits) and len(source_traits) == len(set(source_traits)), "declared source traits must be non-empty and unique")
        require(all_traits == set(source_traits), "observed source traits differ from declared source universe")
    # Explicit false/not-input states prevent omission from being mistaken for a negative association.
    require(len(cells) == len(rows) * len(all_traits), "source membership must explicitly record every row/trait state")
    if rendered is not None:
        plotted = [(r["cluster_id"], r["trait"]) for r in rendered]
        require(len(plotted) == len(set(plotted)), "duplicate displayed member mark")
        require(set(plotted) == expected, "displayed membership differs from accepted exact trait sets")
    if connectors is not None:
        require(trait_order is not None and len(trait_order) == len(set(trait_order)), "connectors require a unique explicit trait order")
        require({trait for key, trait in expected} <= set(trait_order), "trait order omits actual member traits")
        for link in connectors:
            key = link["cluster_id"]
            require(key in rows, "connector uses an unknown cluster")
            require(link["left_trait"] in trait_order and link["right_trait"] in trait_order, "unknown connector endpoint")
            left, right = trait_order.index(link["left_trait"]), trait_order.index(link["right_trait"])
            require(left < right, "connector endpoints must follow the explicit column order")
            require(all((key, trait) in expected for trait in trait_order[left:right+1]),
                    f"{key}: connector crosses a non-member/blank cell")
    return dict(status="PASS", analysis_effect="none", clusters=len(rows), traits=len(all_traits),
                members=len(expected), source_cells=len(cells), strict_pp_threshold=threshold,
                assessed_outside_cluster=sum(a and not b for a, b in cells.values()),
                not_in_regional_input=sum(not a for a, b in cells.values()),
                trait_universe="declared_and_checked" if source_traits is not None else "observed_in_input_only",
                verification_level="source_and_display_mapping" if rendered is not None else "source_contract_only",
                actual_render_validated=False, cluster_records=rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", required=True, type=Path)
    parser.add_argument("--memberships", required=True, type=Path)
    parser.add_argument("--pp-threshold", required=True, type=float, help="Declared strict > cutoff; never selects rows")
    parser.add_argument("--rendered-memberships", type=Path, help="One row per actual plotted member: cluster_id, trait")
    parser.add_argument("--connectors", type=Path)
    parser.add_argument("--trait-order", help="Pipe-separated actual column order, required for connector audit")
    parser.add_argument("--source-traits", help="Pipe-separated trait universe from an independent source manifest; detects deleted all-nonmember columns")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = [args.clusters, args.memberships]
        clusters = table(args.clusters, ["cluster_id", "window_id", "candidate_snp", "cluster_pp", "trait_set"])
        members = table(args.memberships, ["cluster_id", "trait", "in_input", "in_cluster"])
        rendered = table(args.rendered_memberships, ["cluster_id", "trait"]) if args.rendered_memberships else None
        connectors = table(args.connectors, ["cluster_id", "left_trait", "right_trait"]) if args.connectors else None
        result = audit(clusters, members, threshold=args.pp_threshold, rendered=rendered, connectors=connectors,
                       trait_order=args.trait_order.split("|") if args.trait_order else None,
                       source_traits=args.source_traits.split("|") if args.source_traits else None)
        paths += [p for p in [args.rendered_memberships, args.connectors] if p is not None]
        result["source_sha256"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = dict(status="FAIL", error=str(exc), analysis_effect="none", actual_render_validated=False)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
