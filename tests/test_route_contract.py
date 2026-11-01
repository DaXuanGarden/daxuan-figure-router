"""Falsifiable route-evidence tests; no backend, global skills, or AI needed."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_routes.py"
SPEC = importlib.util.spec_from_file_location("route_contract_checker", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def suite():
    return {"suite": "isolated-contract", "cases": [{
        "id": "edit", "prompt": "Only edit this existing R figure.",
        "task_spec": {"mode": "edit", "language": "R", "domain": "general"},
        "expected": {"primary_any_of": ["r-plot"], "must_not_primary": ["analysis-skill"],
                     "allow_existing_code": True, "forbidden_actions": ["choose_chart"],
                     "conditions": ["Preserve the values and the scientific meaning."]},
    }]}


def record():
    return {"case_id": "edit", "execution_target": "existing_code", "primary_skill": None,
            "helpers": [], "language": "R", "read_files": ["fixtures/existing.R"],
            "entry_point": "fixtures/existing.R", "actions": ["inspect_existing_code", "plan_edit", "preserve_results"],
            "verification_level": "route_dry_run"}


class RouteContractTests(unittest.TestCase):
    def check(self, records=None, prompts=None):
        return checker.check_records(prompts if prompts is not None else suite(), records if records is not None else [record()])

    def test_direct_existing_code_is_valid_without_a_primary_skill(self):
        result = self.check()
        self.assertEqual(result["mechanical_checks"], "pass", result)
        self.assertFalse(result["rendering_verified"])
        self.assertFalse(result["evidence_files_checked_for_existence"])
        self.assertFalse(result["free_text_conditions_automatically_verified"])
        self.assertEqual(result["cases"][0]["independent_review_required"], suite()["cases"][0]["expected"]["conditions"])

    def test_empty_missing_duplicate_unknown_and_incomplete_records_fail(self):
        original = record()
        for bad in [[], {}, {"records": []}, [dict(original, case_id="unknown")], [original, original], ["invalid"]]:
            with self.subTest(document=bad):
                self.assertEqual(self.check(bad)["mechanical_checks"], "fail")
        two = suite()
        extra = deepcopy(two["cases"][0]); extra["id"] = "second"
        two["cases"].append(extra)
        self.assertTrue(any("missing case records" in error for error in self.check(prompts=two)["errors"]))
        for field in checker.RECORD_FIELDS:
            bad = record(); del bad[field]
            with self.subTest(missing=field):
                self.assertEqual(self.check([bad])["mechanical_checks"], "fail")

    def test_skill_routes_obey_allowed_and_forbidden_primary(self):
        valid = dict(record(), execution_target="skill", primary_skill="r-plot")
        self.assertEqual(self.check([valid])["mechanical_checks"], "pass")
        for name in ["wrong-plot", "analysis-skill", None, ""]:
            with self.subTest(primary=name):
                self.assertEqual(self.check([dict(valid, primary_skill=name)])["mechanical_checks"], "fail")
        self.assertEqual(self.check([dict(record(), primary_skill="r-plot")])["mechanical_checks"], "fail")
        unauthorized = suite(); unauthorized["cases"][0]["expected"]["allow_existing_code"] = False
        self.assertEqual(self.check(prompts=unauthorized)["mechanical_checks"], "fail")

    def test_hard_language_actions_and_verification_level_are_mechanical(self):
        for changes in [
            {"language": "Python"}, {"language": "unknown"},
            {"actions": []}, {"actions": ["refit_model"]}, {"actions": ["choose_chart"]},
            {"actions": ["I did something undocumented"]}, {"actions": ["render_figure"]},
            {"verification_level": "rendered"}, {"helpers": ["same", "same"]},
            {"read_files": []}, {"read_files": "a.R"}, {"entry_point": ""},
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(self.check([dict(record(), **changes)])["mechanical_checks"], "fail")
        self.assertEqual(self.check([dict(record(), language="r", entry_point=None)])["mechanical_checks"], "pass")

    def test_explicit_skill_cannot_be_silently_replaced(self):
        prompts = suite()
        prompts["cases"][0]["task_spec"]["explicit_skill"] = "requested-skill"
        prompts["cases"][0]["expected"]["primary_any_of"] += ["requested-skill", "native-svg-fallback"]
        requested = dict(record(), execution_target="skill", primary_skill="requested-skill")
        self.assertEqual(self.check([requested], prompts)["mechanical_checks"], "pass")
        fallback = dict(requested, primary_skill="native-svg-fallback", read_files=["/isolated/requested-skill/SKILL.md"], notes="Renderer missing; native local fallback was explicitly authorized.")
        self.assertEqual(self.check([fallback], prompts)["mechanical_checks"], "fail")
        prompts["cases"][0]["expected"]["allow_explicit_fallback"] = True
        self.assertEqual(self.check([fallback], prompts)["mechanical_checks"], "pass")
        for changes in [{"notes": ""}, {"read_files": ["unrelated/SKILL.md"]}, {"read_files": None}, {"primary_skill": "unlisted-fallback"}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.check([dict(fallback, **changes)], prompts)["mechanical_checks"], "fail")

    def test_suite_contract_rejects_contradictions_and_duplicate_cases(self):
        for mutate in [
            lambda x: x["cases"].append(deepcopy(x["cases"][0])),
            lambda x: x["cases"][0]["expected"]["must_not_primary"].append("r-plot"),
            lambda x: x["cases"][0]["task_spec"].update(mode="create"),
            lambda x: x["cases"][0]["expected"].update(allow_explicit_fallback=True),
            lambda x: x["cases"][0]["task_spec"].update(language="Ruby"),
            lambda x: x["cases"][0]["task_spec"].update(mode=[]),
        ]:
            bad = suite(); mutate(bad)
            self.assertTrue(checker.validate_suite(bad))

    def test_catalog_entry_shape_keeps_backend_and_outputs_separate(self):
        point = {"id": "accepted-results", "entry_path": "templates/render.R", "backend": "R",
                 "input_kind": "accepted_results", "required_inputs": ["estimate", "ci_low", "ci_high"],
                 "analysis_effect": "none", "source_kind": "generic_template", "outputs": ["SVG"],
                 "constraints": [], "source_sha256": "a" * 64}
        catalog = {"entries": [{"id": "r-plot", "relative_paths": ["skills/r-plot/SKILL.md"],
                                "languages": ["R"], "backends": ["R"], "outputs": ["SVG"], "entry_points": [point]}]}
        self.assertEqual(checker.validate_catalog(catalog), [])
        for field in checker.ENTRY_FIELDS:
            bad = deepcopy(catalog); del bad["entries"][0]["entry_points"][0][field]
            with self.subTest(missing=field):
                self.assertTrue(checker.validate_catalog(bad))
        for field, value in [("analysis_effect", "probably none"), ("analysis_effect", []),
                             ("required_inputs", "estimate"), ("outputs", "SVG"),
                             ("constraints", {}), ("backend", "SVG"), ("source_sha256", "xyz")]:
            bad = deepcopy(catalog); bad["entries"][0]["entry_points"][0][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(checker.validate_catalog(bad))
        bad = deepcopy(catalog); bad["entries"][0]["languages"] = ["PPTX"]
        self.assertTrue(checker.validate_catalog(bad))

    def test_cli_returns_nonzero_for_invalid_records_and_needs_no_real_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompts = root / "prompts.json"; prompts.write_text(json.dumps(suite()), encoding="utf-8")
            records = root / "records.json"
            command = [sys.executable, "-B", str(SCRIPT), "--prompts", str(prompts), "--records", str(records)]
            for document, expected_exit in [({"records": [record()]}, 0), ([], 1), ([dict(record(), language="python")], 1)]:
                records.write_text(json.dumps(document), encoding="utf-8")
                run = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
                self.assertEqual(run.returncode, expected_exit, run.stdout + run.stderr)
                self.assertFalse(json.loads(run.stdout)["rendering_verified"])
            for invalid_json in ['{"records": [], "records": []}', '{"records": [NaN]}', '{broken']:
                records.write_text(invalid_json, encoding="utf-8")
                run = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(json.loads(run.stdout)["mechanical_checks"], "fail")


if __name__ == "__main__":
    unittest.main()
