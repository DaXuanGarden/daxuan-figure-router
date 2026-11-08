"""Structural FigureBrief and GWAS-recipe tests; no plotting runtime is needed."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "figure_brief.py"
SPEC = importlib.util.spec_from_file_location("figure_brief", SCRIPT)
figure_brief = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(figure_brief)


def valid_brief():
    return {
        "schema_version": "figure-brief.v1",
        "project": "GWAS figure fixture",
        "study_question": "Which accepted results should be visualised?",
        "population": "European-ancestry summary statistics",
        "data_status": "accepted-results",
        "language_preference": "R",
        "scientific_contract": {"claim_boundary": "display only"},
        "input_records": [{"id": "results", "path": "results.tsv", "role": "accepted result table"}],
        "candidate_figures": [{
            "id": "shared_loci", "form": "circular dendrogram", "panel_role": "main",
            "primary_skill": "gwas-figure", "helpers": ["easyplot"],
            "scientific_purpose": "show accepted shared loci",
            "allowed_style_variants": ["compact", "gene-rail"],
            "forbidden_shortcuts": ["do not call annotations causal"]
        }],
        "output_contract": {"required": ["PDF", "SVG", "PNG"], "vector_first": True,
                            "reference_images_are_style_only": True,
                            "human_selection_required_before_production": True},
        "evolution_policy": {"mode": "bounded-human-in-the-loop", "append_only_memory": ["accepted_patterns.jsonl"],
                             "automatic_skill_self_edit": False, "automatic_github_push": False,
                             "promotion_gate": "tests and scientific review"}
    }


class FigureBriefTests(unittest.TestCase):
    def test_project_brief_structure_is_valid_without_reading_data(self):
        # Keep CI independent of the author's local research workspace while
        # still exercising JSON loading and validation through a real file.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "figure-brief.json"
            path.write_text(json.dumps(valid_brief()), encoding="utf-8")
            result = figure_brief.validate_brief(figure_brief.read_json(path), base=path.parent)
        self.assertEqual(result["ok"], True)
        self.assertGreaterEqual(result["candidate_count"], 1)

    def test_invalid_evolution_policy_and_missing_boundaries_fail(self):
        value = valid_brief()
        value["evolution_policy"]["automatic_github_push"] = True
        with self.assertRaises(figure_brief.BriefError):
            figure_brief.validate_brief(value)
        value = valid_brief()
        del value["candidate_figures"][0]["forbidden_shortcuts"]
        with self.assertRaises(figure_brief.BriefError):
            figure_brief.validate_brief(value)

    def test_duplicate_ids_and_unsafe_provenance_fail(self):
        value = valid_brief()
        value["input_records"].append(copy.deepcopy(value["input_records"][0]))
        with self.assertRaises(figure_brief.BriefError):
            figure_brief.validate_brief(value)
        value = valid_brief()
        value["input_records"][0]["path"] = "https://example.invalid/results.tsv"
        with self.assertRaises(figure_brief.BriefError):
            figure_brief.validate_brief(value)

    def test_recipe_catalog_is_structurally_valid_and_never_refits(self):
        catalog = figure_brief.load_recipes(ROOT / "references" / "gwas-figure-recipes.json")
        self.assertGreaterEqual(len(catalog["recipes"]), 6)
        self.assertTrue(all(item["analysis_effect"] == "none" for item in catalog["recipes"].values()))

    def test_check_paths_is_opt_in(self):
        value = valid_brief()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaises(figure_brief.BriefError):
                figure_brief.validate_brief(value, base=base, check_paths=True)
            (base / "results.tsv").write_text("trait\tp\nLST\t1e-8\n", encoding="utf-8")
            self.assertTrue(figure_brief.validate_brief(value, base=base, check_paths=True)["ok"])

    def test_project_root_resolves_project_relative_input_records(self):
        value = valid_brief()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results.tsv").write_text("trait\tp\nLST\t1e-8\n", encoding="utf-8")
            value["project_root"] = "."
            self.assertEqual(figure_brief.validate_brief(value, base=root, check_paths=True)["path_base"], str(root.resolve()))
            value["project_root"] = "missing"
            with self.assertRaises(figure_brief.BriefError):
                figure_brief.validate_brief(value, base=root, check_paths=True)


if __name__ == "__main__":
    unittest.main()
