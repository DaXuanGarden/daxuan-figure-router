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

    def run_cli(self, *arguments, roots=None):
        command = [sys.executable, str(SCRIPT), "--catalog", str(self.catalog)]
        for root in roots if roots is not None else [self.root]:
            command.extend(["--root", str(root)])
        result = subprocess.run(command + list(arguments), cwd=self.base, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
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
        item = self.run_cli("search", "Distinctive continuation")["candidates"][0]
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
        for arguments in [("list",), ("search", "forest"), ("show", "readonly"), ("doctor",)]:
            result = self.run_cli(*arguments)
            self.assertTrue(result["read_only"])
            self.assertNotIn("daxuan-figure-router", [item["name"] for item in result.get("candidates", [])])
        self.assertEqual(self.run_cli("show", "daxuan-figure-router")["candidates"], [])
        self.assertEqual(before, snapshot())


if __name__ == "__main__":
    unittest.main()
