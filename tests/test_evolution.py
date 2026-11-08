"""Bounded figure-memory tests; no network or plotting runtime is needed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "evolution.py"
SPEC = importlib.util.spec_from_file_location("figure_evolution", SCRIPT)
evolution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evolution)


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.memory = self.base / "memory"

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def initialize(self):
        result = self.cli("init", "--memory", self.memory)
        self.assertEqual(result["status"], "initialized")

    def test_append_only_chain_records_choices_failures_and_pending_proposal(self):
        self.initialize()
        image = self.base / "reference.png"
        image.write_bytes(b"not-a-rendered-image-but-a-local-reference-label")
        self.cli("add-reference", "--memory", self.memory, "--id", "ref-01", "--title", "Circular reference",
                 "--kind", "reference-image", "--path", image, "--tag", "circular")
        self.cli("record-choice", "--memory", self.memory, "--variant-id", "circular-gene",
                 "--reason", "Gene links are easier to follow", "--prefer", "arc-links", "--avoid", "dense-labels")
        self.cli("record-failure", "--memory", self.memory, "--area", "legend", "--reason", "Legend clipped",
                 "--action", "Use a dedicated bottom legend band", "--tag", "crop")
        self.cli("propose-rule", "--memory", self.memory,
                 "--proposal", "Prefer a dedicated legend band", "--reason", "Repeated clipping",
                 "--evidence", "reference-000001", "--evidence", "choice-000002", "--evidence", "failure-000003")
        verified = self.cli("check", "--memory", self.memory)
        self.assertEqual(verified["event_count"], 4)
        report = self.cli("summary", "--memory", self.memory)
        self.assertEqual(report["by_kind"]["promotion_request"], 1)
        self.assertEqual(report["preferred_features"], {"arc-links": 1})
        self.assertEqual(report["failure_areas"], {"legend": 1})
        events = (self.memory / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 4)
        self.assertEqual(json.loads(events[-1])["payload"]["status"], "pending-human-review")

    def test_hash_tampering_and_unsafe_reference_are_rejected(self):
        self.initialize()
        self.cli("add-reference", "--memory", self.memory, "--id", "ref-01", "--title", "Reference",
                 "--kind", "layout", "--source-url", "https://example.org/figure")
        events = (self.memory / "events.jsonl").read_text(encoding="utf-8")
        (self.memory / "events.jsonl").write_text(events.replace("Reference", "Changed", 1), encoding="utf-8")
        self.cli("check", "--memory", self.memory, code=2)

        fresh = self.base / "fresh"
        self.cli("init", "--memory", fresh)
        self.cli("add-reference", "--memory", fresh, "--id", "../escape", "--title", "Bad",
                 "--kind", "layout", "--source-url", "https://example.org/figure", code=2)
        self.cli("add-reference", "--memory", fresh, "--id", "ref-02", "--title", "Bad URL",
                 "--kind", "layout", "--source-url", "http://example.org/figure", code=2)

    def test_gallery_is_offline_and_does_not_embed_remote_images(self):
        self.initialize()
        self.cli("add-reference", "--memory", self.memory, "--id", "ref-01", "--title", "Remote provenance",
                 "--kind", "paper", "--source-url", "https://example.org/figure.png")
        gallery = self.base / "gallery.html"
        result = self.cli("gallery", "--memory", self.memory, "--out", gallery)
        self.assertEqual(result["reference_count"], 1)
        page = gallery.read_text(encoding="utf-8")
        self.assertIn("https://example.org/figure.png", page)
        self.assertNotIn('<img src="https://', page)
        self.assertNotIn("<script", page.lower())
        self.assertIn("style-only", page)

    def test_manifest_cannot_enable_automatic_mutation(self):
        self.initialize()
        manifest = json.loads((self.memory / "manifest.json").read_text(encoding="utf-8"))
        manifest["automatic_skill_self_edit"] = True
        (self.memory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.cli("check", "--memory", self.memory, code=2)


if __name__ == "__main__":
    unittest.main()
