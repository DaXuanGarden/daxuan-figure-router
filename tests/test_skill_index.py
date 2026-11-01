"""Exercise discovery against disposable local trees; no installed skills change."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "skill_index.py"


class SkillIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "local-skills"
        self.root.mkdir()
        self.catalog = self.base / "catalog.json"
        self.write_catalog([])

    def write_catalog(self, entries):
        self.catalog.write_text(json.dumps({"schema_version": 1, "scope": "fixture", "entries": entries}))

    def skill(self, relative, name, description, extra=""):
        path = self.root / relative / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n{extra}", encoding="utf-8")
        return path

    def entry(self, identifier, relative, **kwargs):
        source = self.root / relative / "SKILL.md"
        hashes = {relative + "/SKILL.md": hashlib.sha256(source.read_bytes()).hexdigest()} if source.is_file() else {}
        return {
            "id": identifier, "name": identifier, "aliases": [],
            "relative_paths": [relative + "/SKILL.md"], "role": "primary",
            "languages": ["R"], "domains": ["statistics"], "task_tags": ["create"],
            "when": "", "avoid": "", "notes": "", "resource_checks": [],
            "family": identifier, **kwargs,
            "source_hashes": hashes,
        }

    def run_cli(self, *arguments, roots=None, expected_code=0):
        command = [sys.executable, str(SCRIPT), "--catalog", str(self.catalog)]
        for root in roots if roots is not None else [self.root]:
            command.extend(["--root", str(root)])
        result = subprocess.run(command + list(arguments), cwd=self.base, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_explicit_root_isolation_and_precise_catalog_path_binding(self):
        self.skill("package/registered", "shared-name", "Known forest figure")
        self.skill("other/unregistered", "shared-name", "Another forest figure")
        external = self.base / "custom-codex" / "skills" / "outside" / "SKILL.md"
        external.parent.mkdir(parents=True)
        external.write_text("---\nname: outside\ndescription: forest\n---\n")
        self.write_catalog([self.entry("known", "package/registered")])
        result = self.run_cli("list")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(sum(item["registration"] == "reviewed" for item in result["candidates"]), 1)
        self.assertNotIn("outside", [item["name"] for item in result["candidates"]])
        self.write_catalog([self.entry("mapped", str(external.parent))])
        mapped = self.run_cli("show", "mapped", roots=[external.parent.parent])
        self.assertEqual(mapped["candidates"][0]["skill_path"], str(external))

    def test_content_deduplication_name_collisions_aliases_and_symlink_cycles(self):
        first = self.skill("pack-a/directory-one", "shared", "forest plotting")
        copy = self.skill("pack-b/directory-two", "shared", "forest plotting")
        self.skill("pack-c/different", "shared", "volcano plotting")
        (self.root / "alias-one").symlink_to(first.parent, target_is_directory=True)
        (first.parent / "loop").symlink_to(self.root, target_is_directory=True)
        self.write_catalog([
            self.entry("one", "pack-a/directory-one", aliases=["森林图"]),
            self.entry("two", "pack-b/directory-two"),
        ])
        result = self.run_cli("show", "shared")
        self.assertTrue(result["ambiguous"])
        self.assertEqual(len(result["candidates"]), 2)
        one = self.run_cli("show", "森林图")["candidates"][0]
        self.assertEqual(one["catalog_ids"], ["one", "two"])
        self.assertIn(str(first), one["skill_paths"])
        self.assertIn(str(copy), one["skill_paths"])
        self.assertIn(str(self.root / "alias-one" / "SKILL.md"), one["skill_paths"])
        self.assertEqual(len(self.run_cli("show", "directory-two")["candidates"]), 1)
        self.assertTrue(any(item["reason"] == "symlink_cycle_skipped" for item in result["warnings"]))

    def test_nonstandard_frontmatter_retains_multiline_description(self):
        malformed = self.root / "odd-directory" / "SKILL.md"
        malformed.parent.mkdir()
        malformed.write_text("---\nname bad syntax\ndescription: >\n  First line about data.\n  Distinctive continuation phrasing.\ninvalid yaml!\n", encoding="utf-8")
        item = self.run_cli("search", "Distinctive continuation", "--details")["candidates"][0]
        self.assertEqual(item["name"], "odd-directory")
        self.assertIn("First line about data. Distinctive continuation phrasing.", item["description"])
        self.assertIn("frontmatter_unclosed", item["metadata_warnings"])
        quoted = self.skill("quoted", "quoted", '"First sentence\n  Second distinctive sentence"')
        self.assertTrue(quoted.exists())
        self.assertIn("Second distinctive sentence", self.run_cli("show", "quoted")["candidates"][0]["description"])

    def test_resource_deletion_is_checked_live_not_historical_flag(self):
        skill = self.skill("resource-skill", "resource-skill", "chart export")
        asset = skill.parent / "assets" / "template.R"
        asset.parent.mkdir()
        asset.write_text("# fixture")
        self.write_catalog([self.entry("resources", "resource-skill", resource_checks=[
            {"path": "assets/template.R", "exists": True, "required": True, "notes": "historical observation"},
            {"path": "../sibling/scripts", "exists": True, "required": False},
        ])])
        before = self.run_cli("show", "resources")["candidates"][0]["installations"][0]
        self.assertTrue(before["resources"][0]["exists"])
        asset.unlink()
        after = self.run_cli("show", "resources")["candidates"][0]["installations"][0]
        self.assertFalse(after["resources"][0]["exists"])
        self.assertEqual(after["resource_state"], "missing_required")
        self.assertEqual(after["runtime"], "untested")
        self.assertEqual(len(self.run_cli("doctor")["resource_issues"]), 1)
        skill.write_text(skill.read_text() + "\nUpdated instructions.\n")
        changed = self.run_cli("show", "resources")["candidates"][0]
        self.assertEqual(changed["source_state"], "changed_since_review")
        self.assertEqual(changed["registration"], "review_required")

    def test_new_unregistered_skills_are_discoverable_without_assumed_capabilities(self):
        self.skill("brand-new", "brand-new", "quasar custom diagram")
        result = self.run_cli("search", "quasar")
        item = result["candidates"][0]
        self.assertEqual(item["registration"], "unreviewed")
        self.assertEqual(item["languages"], [])
        self.assertEqual(result["selection_status"], "candidates_require_skill_read")
        self.assertEqual(self.run_cli("search", "quasar", "--role", "primary")["candidates"], [])
        review = self.run_cli("search", "quasar", "--role", "primary")["review_candidates"][0]
        self.assertEqual(review["filter_status"], "requires_source_read_not_compatible")

    def test_language_and_role_filters_use_explicit_catalog_metadata(self):
        entries = []
        for identifier, languages, role in [
            ("r-plot", ["R"], "primary"), ("py-plot", ["Python"], "primary"),
            ("palette", ["language-independent"], "helper"),
        ]:
            self.skill(identifier, identifier, "plot charts")
            entries.append(self.entry(identifier, identifier, languages=languages, role=role))
        self.skill("unknown", "unknown", "plot charts")
        self.write_catalog(entries)
        r_ids = {item["id"] for item in self.run_cli("search", "plot", "--language", "R")["candidates"]}
        self.assertEqual(r_ids, {"r-plot", "palette"})
        self.assertEqual(self.run_cli("list", "--role", "helper")["candidates"][0]["id"], "palette")
        self.assertEqual(self.run_cli("search", "--language", "python", "--tag", "create", "--domain", "statistics")["total_matches"], 2)

    def test_no_match_is_empty_and_negative_catalog_text_does_not_rank(self):
        self.skill("one", "one", "forest plot")
        self.skill("two", "two", "forest chart")
        self.write_catalog([self.entry("one", "one", avoid="never use for quuxzz", notes="quuxzz unsupported")])
        self.assertEqual(self.run_cli("search", "quuxzz")["candidates"], [])
        result = self.run_cli("search", "forest", "--limit", "1")
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(self.run_cli("show", "missing-id")["candidates"], [])

    def test_commands_do_not_write_indexes_or_execute_resources(self):
        skill = self.skill("readonly", "readonly", "forest plot")
        self.skill("installed-router-copy", "daxuan-figure-router", "forest plot router")
        resource = skill.parent / "script.py"
        resource.write_text("from pathlib import Path\nPath('executed-marker').write_text('bad')\n")
        self.write_catalog([self.entry("readonly", "readonly", resource_checks=[{"path": "script.py", "required": True}])])

        def snapshot():
            return {str(path.relative_to(self.base)): (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in self.base.rglob("*") if path.is_file()}

        before = snapshot()
        for arguments in [("list",), ("search", "forest"), ("show", "readonly"), ("doctor",), ("vocabulary",)]:
            result = self.run_cli(*arguments)
            self.assertTrue(result["read_only"])
            self.assertNotIn("daxuan-figure-router", [item["name"] for item in result.get("candidates", [])])
        self.assertEqual(self.run_cli("show", "daxuan-figure-router")["candidates"], [])
        self.assertEqual(before, snapshot())

    def test_stale_cards_are_history_not_current_filter_or_search_evidence(self):
        source = self.skill("portable", "portable", "R legacy rendering")
        self.write_catalog([self.entry("portable-legacyquux", "portable", aliases=["legacyquux"], languages=["R"],
                                       domains=["gwas"], task_tags=["legacyquux"], when="legacyquux rendering")])
        source.write_text("---\nname: portable\ndescription: Python quasar rendering\n---\n", encoding="utf-8")
        current = self.run_cli("show", "portable")["candidates"][0]
        self.assertEqual(current["source_state"], "changed_since_review")
        self.assertEqual(current["backends"], [])
        self.assertEqual(current["domains"], [])
        self.assertEqual(current["task_tags"], [])
        self.assertEqual(current["catalog_entries"][0]["languages"], ["R"])
        self.assertEqual(self.run_cli("search", "legacyquux")["candidates"], [])
        self.assertEqual(len(self.run_cli("search", "portable-legacyquux")["candidates"]), 1)
        result = self.run_cli("search", "quasar", "--language", "python", "--role", "primary")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["total_review_matches"], 1)
        self.assertEqual(result["review_candidates"][0]["registration"], "review_required")
        self.assertNotEqual(result["review_candidates"][0]["filter_status"], "reviewed_filters_match")

    def test_new_and_moved_candidates_remain_bounded_but_known_mismatch_does_not_fallback(self):
        original = self.skill("old-location", "moved-plot", "quasar plotting")
        entry = self.entry("old-location", "old-location")
        destination = self.root / "new-location" / "SKILL.md"
        destination.parent.mkdir()
        original.rename(destination)
        for number in range(4):
            self.skill(f"new-{number}", f"new-{number}", f"quasar plotting {number}")
        self.skill("known-python", "known-python", "quasar plotting")
        self.write_catalog([entry, self.entry("known-python", "known-python", languages=["Python"])])
        result = self.run_cli("search", "quasar", "--language", "R", "--review-limit", "2")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["total_review_matches"], 5)
        self.assertEqual(len(result["review_candidates"]), 2)
        self.assertNotIn("known-python", [item["id"] for item in result["review_candidates"]])
        moved = self.run_cli("show", "moved-plot")["candidates"][0]
        self.assertEqual(moved["catalog_ids"], [])
        self.assertEqual(moved["registration"], "unreviewed")
        self.assertEqual(self.run_cli("doctor")["catalog_not_discovered"][0]["id"], "old-location")

    def test_summaries_are_compact_and_expansion_is_explicit(self):
        self.skill("one", "one", "forest plot")
        self.write_catalog([self.entry("one", "one")])
        for command in [("search", "forest"), ("list",)]:
            result = self.run_cli(*command)
            self.assertEqual(result["schema_version"], 2)
            self.assertNotIn("catalog_entries", result["candidates"][0])
            self.assertNotIn("installations", result["candidates"][0])
            self.assertIn("installations", self.run_cli(*command, "--details")["candidates"][0])
        self.assertIn("installations", self.run_cli("show", "one")["candidates"][0])

    def test_vocabulary_domain_aliases_and_unknown_filter_diagnostics(self):
        for identifier in ["general", "medical"]:
            self.skill(identifier, identifier, "forest plot")
        self.write_catalog([self.entry(identifier, identifier, domains=[identifier], task_tags=["forest"])
                            for identifier in ["general", "medical"]])
        words = self.run_cli("vocabulary")
        self.assertEqual(words["domain_aliases"], {"generic": "general", "clinical": "medical"})
        for alias, canonical in [("generic", "general"), ("clinical", "medical")]:
            aliased = self.run_cli("search", "forest", "--domain", alias)
            self.assertEqual(aliased["candidates"], self.run_cli("search", "forest", "--domain", canonical)["candidates"])
            self.assertEqual(aliased["filter_normalizations"], [{"filter": "domain", "requested": alias, "applied": canonical}])
        bad = self.run_cli("search", "forest", "--domain", "unlisted", "--tag", "unlisted", expected_code=2)
        self.assertEqual(bad["error"], "unknown_filter_value")
        self.assertEqual({item["filter"] for item in bad["diagnostics"]}, {"tag", "domain"})
        self.assertIn("medical", bad["diagnostics"][0]["available_values"])

    def test_auxiliary_intents_explain_language_scope_and_output_is_not_backend(self):
        specifications = [("palette", "palette"), ("qa", "final-qa"),
                          ("reconstruct", "image-to-ppt"), ("reference", "template-search")]
        entries = []
        for intent, tag in specifications:
            self.skill(intent, intent, "quasar helper")
            entries.append(self.entry(intent, intent, languages=["PPTX"], backends=[], outputs=["PPTX"],
                                      role="helper", intents=[intent], task_tags=[tag]))
        self.write_catalog(entries)
        for intent, tag in specifications:
            result = self.run_cli("search", "quasar", "--language", "R", "--intent", intent)
            self.assertEqual([item["id"] for item in result["candidates"]], [intent])
            self.assertEqual(result["filter_scope"]["effective_language"], "any")
            self.assertEqual(result["candidates"][0]["backends"], [])
            self.assertEqual(self.run_cli("search", "quasar", "--language", "R", "--tag", tag)["total_matches"], 1)
        self.assertEqual(self.run_cli("search", "quasar", "--language", "R", "--intent", "edit")["candidates"], [])

    def test_lexical_evidence_chinese_extraction_and_domain_priority(self):
        self.skill("general", "general", "General forest plot and map chart")
        self.skill("genetics", "genetics", "forest map forest map heatmap")
        self.skill("heatmap", "heatmap", "Heatmap drawing")
        self.write_catalog([
            self.entry("general", "general", domains=["general"], task_tags=["forest", "map"]),
            self.entry("genetics", "genetics", domains=["gwas"], task_tags=["forest", "map", "magma"]),
            self.entry("heatmap", "heatmap", domains=["general"], task_tags=["heatmap"]),
        ])
        result = self.run_cli("search", "我有已经算好的HR和置信区间，请帮我画一张森林图")
        self.assertIn("forest", result["query_terms"])
        self.assertEqual(result["candidates"][0]["id"], "general")
        self.assertEqual(self.run_cli("search", "map")["candidates"][0]["id"], "general")
        self.assertEqual(self.run_cli("search", "gwas forest")["candidates"][0]["id"], "genetics")
        self.assertEqual(self.run_cli("search", "magma")["candidates"][0]["id"], "genetics")
        detailed = self.run_cli("search", "map", "--details")
        heatmap = next(item for item in detailed["candidates"] if item["id"] == "heatmap")
        self.assertTrue(all(item["match"] == "substring" for item in heatmap["evidence"]))
        self.assertFalse(any("avoid" in item["field"] or "notes" in item["field"]
                             for candidate in detailed["candidates"] for item in candidate["evidence"]))
        self.assertEqual(self.run_cli("search", "完全无法命中的独特词句")["candidates"], [])

    def test_entry_points_check_actual_source_without_runtime_claims(self):
        skill = self.skill("renderer", "renderer", "forest rendering")
        code = skill.parent / "renderer.R"
        code.write_text("# render accepted results\n")
        point = {"id": "renderer", "entry_path": "renderer.R", "backend": "R",
                 "input_kind": "accepted_results", "analysis_effect": "none",
                 "source_sha256": hashlib.sha256(code.read_bytes()).hexdigest()}
        self.write_catalog([self.entry("renderer", "renderer", entry_points=[point])])
        before = self.run_cli("show", "renderer")["candidates"][0]["entry_points"][0]
        self.assertEqual(before["source_state"], "unchanged")
        self.assertEqual(before["contract_state"], "reviewed_source")
        self.assertEqual(before["runtime"], "untested")
        code.write_text("# changed entry\n")
        changed = self.run_cli("show", "renderer")["candidates"][0]["entry_points"][0]
        self.assertEqual(changed["source_state"], "changed_since_review")
        self.assertEqual(changed["contract_state"], "historical_only")
        self.assertEqual(len(self.run_cli("doctor")["entry_point_issues"]), 1)
        code.unlink()
        missing = self.run_cli("show", "renderer")["candidates"][0]["entry_points"][0]
        self.assertEqual(missing["source_state"], "missing")
        self.assertFalse(missing["exists"])

    def test_reviewed_representative_does_not_point_to_unregistered_content_copy(self):
        first = self.skill("a-unregistered", "renderer", "forest renderer")
        registered = self.skill("z-registered", "renderer", "forest renderer")
        self.write_catalog([self.entry("renderer", "z-registered")])
        result = self.run_cli("search", "forest", "--language", "R")["candidates"][0]
        self.assertEqual(result["skill_path"], str(registered))
        detailed = self.run_cli("show", "renderer")["candidates"][0]
        self.assertEqual(detailed["reviewed_skill_paths"], [str(registered)])
        unregistered = next(item for item in detailed["installations"] if item["skill_path"] == str(first))
        self.assertEqual(unregistered["resources"], [])
        self.assertEqual(unregistered["registration"], "unreviewed")

    def test_unknown_backend_is_reviewable_while_known_language_mismatch_is_excluded(self):
        for identifier in ["unknown-ppt", "python-ppt", "incomplete-card"]:
            self.skill(identifier, identifier, "quasar editable slide reconstruction")
        self.write_catalog([
            self.entry("unknown-ppt", "unknown-ppt", backends=[], languages=[], outputs=["PPTX"],
                       intents=["reconstruct"], task_tags=["editable-reconstruction"]),
            self.entry("python-ppt", "python-ppt", backends=["Python"], intents=["reconstruct"],
                       task_tags=["editable-reconstruction"]),
            self.entry("incomplete-card", "incomplete-card", backends=["R"], intents=[], task_tags=[]),
        ])
        result = self.run_cli("search", "quasar", "--language", "R")
        self.assertEqual([item["id"] for item in result["candidates"]], ["incomplete-card"])
        self.assertEqual([item["id"] for item in result["review_candidates"]], ["unknown-ppt"])
        self.assertEqual(result["review_candidates"][0]["unknown_filter_fields"], ["language"])
        incomplete = self.run_cli("search", "quasar", "--language", "R", "--intent", "create")
        self.assertEqual([item["id"] for item in incomplete["review_candidates"]], ["incomplete-card"])
        self.assertEqual(incomplete["review_candidates"][0]["unknown_filter_fields"], ["intent"])
        self.assertEqual(self.run_cli("show", "python-ppt", "--language", "R")["candidates"][0]["filter_status"], "known_filter_mismatch")

    def test_empty_query_does_not_recommend_arbitrary_unreviewed_skills(self):
        self.skill("registered", "registered", "editable slide reconstruction")
        self.skill("ablation", "ablation", "ablation planning")
        self.skill("writing", "writing", "manuscript writing")
        self.write_catalog([self.entry("registered", "registered", backends=[], intents=["reconstruct"],
                                       task_tags=["editable-reconstruction"])])
        result = self.run_cli("search", "--tag", "editable-reconstruction", "--intent", "reconstruct", "--language", "R")
        self.assertEqual([item["id"] for item in result["candidates"]], ["registered"])
        self.assertEqual(result["review_candidates"], [])
        self.assertEqual(result["total_review_matches"], 0)
        self.assertEqual(result["review_pending_without_query"], 2)
        self.assertIn("keywords", result["review_hint"])
        query = self.run_cli("search", "ablation", "--tag", "editable-reconstruction", "--intent", "reconstruct", "--language", "R")
        self.assertEqual(len(query["review_candidates"]), 1)
        self.assertEqual(query["review_candidates"][0]["name"], "ablation")


if __name__ == "__main__":
    unittest.main()
