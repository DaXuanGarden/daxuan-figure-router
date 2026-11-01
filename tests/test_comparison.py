"""Real stdlib PNG fixtures and negative integrity tests; no drawing runtime."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "comparison.py"
SPEC = importlib.util.spec_from_file_location("figure_comparison", SCRIPT)
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_bytes(seed=10, width=3, height=2, metadata=b"", filter_method=0):
    rows = [bytes((seed + x + y) % 256 for x in range(width * 3)) for y in range(height)]
    encoded = []
    previous = bytes(width * 3)
    for row in rows:
        filtered = []
        for i, value in enumerate(row):
            left, above = row[i - 3] if i >= 3 else 0, previous[i]
            upper_left = previous[i - 3] if i >= 3 else 0
            prediction = (0, left, above, (left + above) // 2, comparison._paeth(left, above, upper_left))[filter_method]
            filtered.append((value - prediction) & 255)
        encoded.append(bytes([filter_method]) + bytes(filtered))
        previous = row
    header = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    comment = chunk(b"tEXt", b"note\x00" + metadata) if metadata else b""
    return b"\x89PNG\r\n\x1a\n" + header + comment + chunk(b"IDAT", zlib.compress(b"".join(encoded))) + chunk(b"IEND", b"")


def sample_png(width, height, depth, color, scanlines, palette=b"", transparency=b"", interlace=0):
    header = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, interlace))
    palette_chunk = chunk(b"PLTE", palette) if palette else b""
    transparent_chunk = chunk(b"tRNS", transparency) if transparency else b""
    return (b"\x89PNG\r\n\x1a\n" + header + palette_chunk + transparent_chunk
            + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.input = self.base / "accepted.csv"
        self.input.write_text("term,estimate,low,high,group\nA,1.2,0.9,1.5,g1\nB,0.8,0.5,1.1,g2\n")
        self.analysis = {"family": "forest", "inference_scope": "supplied estimates", "rows": 2, "reference": 1.0}
        self.baseline = self.base / "baseline.json"
        self.write(self.baseline, self.analysis)
        self.brief = self.base / "brief.json"
        self.brief_value = {"schema_version": 1, "title": "Accepted-result alternatives", "input_file": self.input.name,
                            "language": "python", "canvas_mm": [180, 120],
                            "data_contract": {"state": "accepted_results", "estimate": "estimate", "interval": "95% CI"},
                            "analysis_file": self.baseline.name,
                            "variants": [self.variant("interval", "interval forest"), self.variant("linked", "reference-linked forest")]}
        self.write(self.brief, self.brief_value)
        self.run = self.base / "comparison"
        self.results_dir = self.base / "outputs"
        self.results_dir.mkdir()
        self.results_file = self.results_dir / "results.json"

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def variant(self, identifier, form, style="pastel"):
        return {"id": identifier, "title": identifier.title(), "form": form, "style_family": style,
                "rationale": "Show supplied estimates without refitting.", "primary_skill": "make-sci-data-figures",
                "helpers": ["sci-color-palettes"], "entry_point": "scripts/advanced_template_workbench.py forest"}

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], cwd=self.base,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def plan(self):
        result = self.cli("plan", "--brief", self.brief, "--outdir", self.run)
        self.plan_value = json.loads((self.run / "plan.json").read_text())
        self.assertEqual(result["rendered_count"], 0)
        return result

    def receipts(self, qa="unreviewed"):
        result = []
        for i, variant in enumerate(self.plan_value["variants"]):
            stem = self.results_dir / variant["id"]
            stem.with_suffix(".png").write_bytes(png_bytes(seed=10 + i * 20))
            self.write(stem.with_suffix(".json"), self.analysis)
            self.write(stem.with_suffix(".geometry.json"), {"xlim": [0.4, 1.6], "ylim": [-0.5, 1.5]})
            stem.with_suffix(".py").write_text("# renderer evidence, never executed by the collector\n")
            result.append({"id": variant["id"], "status": "rendered", "preview": stem.name + ".png",
                           "language": "python", "canvas_mm": [180, 120],
                           "data_sha256": self.plan_value["data_sha256"], "science_sha256": self.plan_value["science_sha256"],
                           "analysis_file": stem.name + ".json", "code": stem.name + ".py",
                           "qa": {"status": qa, "notes": "Draft preview inspected", "evidence": [stem.name + ".geometry.json"]},
                           "provenance": {"source": "actual local accepted-result helper", "analysis_effect": "none"}})
        self.write(self.results_file, {"variants": result})
        return result

    def assemble(self, code=0):
        return self.cli("assemble", "--plan", self.run / "plan.json", "--results", self.results_file, code=code)

    def ready(self, qa="unreviewed"):
        self.plan()
        self.receipts(qa)
        self.assemble()

    def test_complete_cli_offline_gallery_and_append_only_selection(self):
        original_data = self.input.read_bytes()
        self.ready()
        check = self.cli("check", "--run", self.run)
        self.assertEqual(check["rendered_count"], 2)
        self.assertEqual(check["selection_count"], 0)
        page = (self.run / "gallery.html").read_text()
        self.assertIn("grid-template-columns:1fr", page)
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("Export choice request", page)
        self.assertIn('src="assets/interval/preview.png"', page)
        self.assertNotIn("<iframe", page)
        self.assertNotIn("<object", page)
        first = self.cli("select", "--run", self.run, "--id", "interval", "--reason", "Clearer intervals")
        self.assertEqual(first["selection_scope"], "for_refinement")
        history = self.run / "selection-history.jsonl"
        first_bytes = history.read_bytes()
        second = self.cli("select", "--run", self.run, "--id", "linked", "--reason", "Prefer reference links")
        self.assertEqual(second["selection_count"], 2)
        self.assertTrue(history.read_bytes().startswith(first_bytes))
        events = [json.loads(x) for x in history.read_text().splitlines()]
        self.assertEqual(events[1]["previous_event_sha256"], events[0]["event_sha256"])
        self.assertEqual(json.loads((self.run / "selection.json").read_text()), events[-1])
        self.assertEqual(self.cli("check", "--run", self.run)["selection_count"], 2)
        self.assertTrue((self.run / "assets/interval/preview.png").is_file())
        self.assertEqual(self.input.read_bytes(), original_data)

    def test_choice_request_import_is_bound_to_plan(self):
        self.ready()
        request = self.base / "choice.json"
        self.write(request, {"schema_version": 1, "plan_sha256": "0" * 64, "variant_id": "interval", "reason": "Readable"})
        self.cli("select", "--run", self.run, "--choice", request, code=2)
        self.assertFalse((self.run / "selection-history.jsonl").exists())
        value = json.loads(request.read_text())
        value["plan_sha256"] = self.plan_value["plan_sha256"]
        self.write(request, value)
        result = self.cli("select", "--run", self.run, "--choice", request)
        self.assertEqual(result["selected_variant_id"], "interval")

    def test_refuses_existing_run_and_reassembly_without_mutation(self):
        self.ready()
        before = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        self.cli("plan", "--brief", self.brief, "--outdir", self.run, code=2)
        self.assemble(code=2)
        self.assertEqual(before, {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()})

    def test_rejects_bad_brief_ids_duplicate_pairs_and_missing_design(self):
        for mutate in (
            lambda b: b["variants"][0].update(id="../../escape"),
            lambda b: b["variants"][1].update(id="interval"),
            lambda b: b["variants"][1].update(form=b["variants"][0]["form"]),
            lambda b: b.update(data_contract={}),
            lambda b: b.update(canvas_mm=[float("nan"), 120]),
            lambda b: b.update(variants=b["variants"][:1]),
        ):
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(self.brief_value)
                mutate(value)
                self.write(self.brief, value)
                self.cli("plan", "--brief", self.brief, "--outdir", self.run, code=2)
                self.assertFalse(self.run.exists())

    def test_results_require_exactly_one_row_per_planned_id(self):
        self.plan()
        rows = self.receipts()
        for values in (rows[:1], rows + rows[:1], rows + [{"id": "unknown", "status": "blocked", "reason": "not planned"}]):
            with self.subTest(values=len(values)):
                self.write(self.results_file, {"variants": values})
                self.assemble(code=2)
                self.assertFalse((self.run / "gallery.json").exists())

    def test_receipt_contract_failures_are_visible_and_not_rendered(self):
        for key, value in (("data_sha256", "0" * 64), ("science_sha256", "0" * 64),
                           ("language", "R"), ("canvas_mm", [120, 180]), ("preview", "missing.png"),
                           ("qa", {"status": "excellent"})):
            with self.subTest(key=key):
                self.run = self.base / ("case-" + key)
                self.plan()
                rows = self.receipts()
                rows[1][key] = value
                self.write(self.results_file, {"variants": rows})
                result = self.assemble(code=1)
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["rendered_count"], 1)
                self.assertEqual(self.cli("check", "--run", self.run, code=1)["status"], "partial")
                manifest = json.loads((self.run / "gallery.json").read_text())
                self.assertEqual(manifest["variants"][1]["status"], "invalid")
                self.assertFalse((self.run / "assets/linked").exists())
                self.cli("select", "--run", self.run, "--id", "linked", "--reason", "invalid choice", code=2)

    def test_actual_analysis_is_canonical_and_checked_against_frozen_baseline(self):
        self.plan()
        rows = self.receipts()
        (self.results_dir / "interval.json").write_text('{"reference":1.0,"rows":2,"inference_scope":"supplied estimates","family":"forest"}')
        self.assemble()
        self.assertTrue(self.cli("check", "--run", self.run)["ok"])
        self.run = self.base / "different-analysis"
        self.plan()
        rows = self.receipts()
        self.write(self.results_dir / "linked.json", {**self.analysis, "reference": 0})
        result = self.assemble(code=1)
        self.assertIn("analysis JSON differs", " ".join(result["issues"]))

    def test_analysis_consistency_required_even_without_declared_baseline(self):
        self.brief_value.pop("analysis_file")
        self.write(self.brief, self.brief_value)
        self.plan()
        self.receipts()
        self.write(self.results_dir / "linked.json", {**self.analysis, "rows": 3})
        self.assemble(code=1)
        self.assertIn("analysis JSON differs", (self.run / "gallery.json").read_text())

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_analysis(self):
        for value in ('{"rows":2,"rows":3}', '{"rows":NaN}', '{"rows":Infinity}', '{"rows":1e999}'):
            with self.subTest(value=value):
                self.run = self.base / ("invalid-json-" + str(len(list(self.base.glob("invalid-json-*")))))
                self.plan()
                self.receipts()
                (self.results_dir / "linked.json").write_text(value)
                self.assemble(code=1)

    def test_duplicate_pixels_ignored_metadata_and_png_filters(self):
        self.plan()
        self.receipts()
        first, second = self.results_dir / "interval.png", self.results_dir / "linked.png"
        second.write_bytes(png_bytes(seed=10, metadata=b"different metadata", filter_method=1))
        self.assertNotEqual(first.read_bytes(), second.read_bytes())
        result = self.assemble(code=1)
        self.assertEqual(result["rendered_count"], 0)
        self.assertTrue(all(x["status"] == "invalid" for x in json.loads((self.run / "gallery.json").read_text())["variants"]))
        self.cli("check", "--run", self.run, code=1)

    def test_rgb_and_opaque_rgba_do_not_create_fake_candidate_diversity(self):
        self.plan()
        self.receipts()
        pixels = bytes([20, 30, 40]) * 3
        opaque = bytes([20, 30, 40, 255]) * 3
        (self.results_dir / "interval.png").write_bytes(sample_png(3, 2, 8, 2, (b"\x00" + pixels) * 2))
        (self.results_dir / "linked.png").write_bytes(sample_png(3, 2, 8, 6, (b"\x00" + opaque) * 2))
        result = self.assemble(code=1)
        self.assertEqual(result["rendered_count"], 0)
        self.assertIn("Duplicate PNG content", " ".join(result["issues"]))
        self.assertEqual(self.cli("check", "--run", self.run, code=1)["rendered_count"], 0)

    def test_partial_blocked_and_qa_failed_are_distinct_and_not_selectable(self):
        self.plan()
        rows = self.receipts(qa="fail")
        rows[1] = {"id": "linked", "status": "blocked", "reason": "Renderer dependency missing"}
        self.write(self.results_file, {"variants": rows})
        result = self.assemble(code=1)
        self.assertEqual(result["rendered_count"], 1)
        page = (self.run / "gallery.html").read_text()
        self.assertIn("QA failed", page)
        self.assertIn("Blocked", page)
        self.assertNotIn('data-choice="', page)
        for identifier in ("interval", "linked", "unknown"):
            self.cli("select", "--run", self.run, "--id", identifier, "--reason", "Choose", code=2)
        self.assertFalse((self.run / "selection-history.jsonl").exists())

    def test_valid_choice_in_partial_comparison_is_recorded_but_returns_partial(self):
        self.plan()
        rows = self.receipts()
        rows[1] = {"id": "linked", "status": "blocked", "reason": "Missing renderer"}
        self.write(self.results_file, {"variants": rows})
        self.assemble(code=1)
        result = self.cli("select", "--run", self.run, "--id", "interval", "--reason", "Use available candidate", code=1)
        self.assertTrue(result["action_success"])
        self.assertEqual(result["status"], "selected_partial")
        self.assertEqual(self.cli("check", "--run", self.run, code=1)["selection_count"], 1)

    def test_mutated_snapshots_plan_assets_html_and_analysis_block_check_and_select(self):
        for name in ("data", "plan", "preview", "analysis", "html", "qa", "code"):
            with self.subTest(name=name):
                self.run = self.base / ("tamper-" + name)
                self.ready()
                target = {"data": self.run / self.plan_value["input_file"], "plan": self.run / "plan.json",
                          "preview": self.run / "assets/interval/preview.png", "analysis": self.run / "assets/interval/analysis.json",
                          "html": self.run / "gallery.html", "qa": self.run / "assets/interval/qa-0.txt",
                          "code": self.run / "assets/interval/code.py"}[name]
                target.write_bytes(target.read_bytes() + b"\nchanged")
                self.cli("check", "--run", self.run, code=2)
                self.cli("select", "--run", self.run, "--id", "interval", "--reason", "Should refuse tampered evidence", code=2)
                self.assertFalse((self.run / "selection-history.jsonl").exists())

    def test_symlinked_or_traversal_stored_assets_are_rejected(self):
        self.ready()
        preview = self.run / "assets/interval/preview.png"
        preview.unlink()
        preview.symlink_to(self.results_dir / "interval.png")
        self.cli("check", "--run", self.run, code=2)
        preview.unlink()
        preview.write_bytes((self.results_dir / "interval.png").read_bytes())
        manifest = json.loads((self.run / "gallery.json").read_text())
        manifest["variants"][0]["preview"]["path"] = "../outputs/interval.png"
        manifest.pop("gallery_sha256")
        self.write(self.run / "gallery.json", comparison.sealed(manifest, "gallery_sha256"))
        result = self.cli("check", "--run", self.run, code=2)
        self.assertIn("Unsafe stored path", result["message"])

    def test_html_escapes_untrusted_metadata_and_preserves_local_links(self):
        attack = '</script><script src="https://bad.example/x.js">alert(1)</script>'
        self.brief_value["title"] = attack
        self.brief_value["variants"][0]["title"] = attack
        self.brief_value["variants"][0]["rationale"] = '<img src="https://bad.example/track">'
        self.write(self.brief, self.brief_value)
        self.plan()
        rows = self.receipts()
        rows[0]["qa"]["notes"] = attack
        rows[0]["provenance"] = {"html": attack}
        self.write(self.results_file, {"variants": rows})
        self.assemble()
        page = (self.run / "gallery.html").read_text()
        self.assertNotIn(attack, page)
        self.assertIn("&lt;/script&gt;", page)
        self.assertNotIn('src="https://', page)
        self.assertNotIn('href="javascript:', page)
        self.assertNotIn(str(self.results_dir), page)

    def test_history_corruption_latest_mismatch_and_empty_reason_do_not_append(self):
        self.ready()
        self.cli("select", "--run", self.run, "--id", "interval", "--reason", "Initial choice")
        history = self.run / "selection-history.jsonl"
        latest = self.run / "selection.json"
        first, last = history.read_bytes(), latest.read_bytes()
        self.cli("select", "--run", self.run, "--id", "linked", "--reason", " ", code=2)
        self.assertEqual(history.read_bytes(), first)
        latest.write_text("{}")
        self.cli("select", "--run", self.run, "--id", "linked", "--reason", "Do not overwrite broken latest", code=2)
        self.assertEqual(history.read_bytes(), first)
        latest.write_bytes(last)
        history.write_bytes(first[:-1])
        self.cli("check", "--run", self.run, code=2)
        self.cli("select", "--run", self.run, "--id", "linked", "--reason", "Do not repair by truncation", code=2)
        self.assertEqual(history.read_bytes(), first[:-1])

    def test_unicode_line_separators_do_not_split_jsonl_events(self):
        self.ready()
        reason = "Clear\u0085labels\u2028and\u2029intervals"
        self.cli("select", "--run", self.run, "--id", "interval", "--reason", reason)
        self.assertEqual(self.cli("check", "--run", self.run)["selection_count"], 1)
        self.cli("select", "--run", self.run, "--id", "linked", "--reason", "Second choice")
        history = (self.run / "selection-history.jsonl").read_text()
        self.assertEqual(json.loads(history.split("\n")[0])["reason"], reason)

    def test_latest_publication_failure_preserves_committed_journal_and_is_repairable(self):
        self.ready()
        comparison.select_command(self.run, "interval", "First committed choice")
        history, latest = self.run / "selection-history.jsonl", self.run / "selection.json"
        initial_history, initial_latest = history.read_bytes(), latest.read_bytes()
        original_replace = comparison.os.replace

        def fail_latest(source, destination):
            if Path(destination).name == "selection.json":
                raise OSError("simulated latest publication disk failure")
            return original_replace(source, destination)

        with mock.patch.object(comparison.os, "replace", side_effect=fail_latest):
            failed = comparison.select_command(self.run, "linked", "Second choice committed before cache failure")
        self.assertFalse(failed["ok"])
        self.assertFalse(failed["action_success"])
        self.assertTrue(failed["selection_committed"])
        self.assertEqual(failed["status"], "selection_committed_latest_stale")
        self.assertTrue(history.read_bytes().startswith(initial_history))
        self.assertEqual(latest.read_bytes(), initial_latest)
        committed_history = history.read_bytes()
        checked = self.cli("check", "--run", self.run, code=1)
        self.assertEqual(checked["latest_selection_status"], "stale")
        self.assertEqual(checked["selection_count"], 2)
        self.assertEqual(checked["selected_variant_id"], "linked")
        self.assertEqual(history.read_bytes(), committed_history)  # check is read-only
        self.cli("select", "--run", self.run, "--id", "interval", "--reason", "Needs explicit repair first", code=2)
        repaired = self.cli("repair-latest", "--run", self.run)
        self.assertEqual(repaired["status"], "latest_repaired")
        self.assertEqual(json.loads(latest.read_text())["sequence"], 2)
        self.assertEqual(history.read_bytes(), committed_history)
        self.assertEqual(self.cli("select", "--run", self.run, "--id", "interval", "--reason", "New choice after recovery")["selection_count"], 3)

    def test_first_selection_latest_failure_and_missing_cache_are_repairable(self):
        self.ready()
        original_replace = comparison.os.replace

        def fail_latest(source, destination):
            if Path(destination).name == "selection.json":
                raise PermissionError("simulated permission failure publishing latest")
            return original_replace(source, destination)

        with mock.patch.object(comparison.os, "replace", side_effect=fail_latest):
            failed = comparison.select_command(self.run, "interval", "First durable journal event")
        self.assertTrue(failed["selection_committed"])
        self.assertFalse((self.run / "selection.json").exists())
        checked = self.cli("check", "--run", self.run, code=1)
        self.assertEqual(checked["latest_selection_status"], "missing")
        self.assertEqual(checked["selection_count"], 1)
        self.cli("repair-latest", "--run", self.run)
        self.cli("check", "--run", self.run)

    def test_journal_publication_failure_does_not_append_a_partial_event(self):
        self.ready()
        comparison.select_command(self.run, "interval", "Existing committed choice")
        history, latest = self.run / "selection-history.jsonl", self.run / "selection.json"
        initial_history, initial_latest = history.read_bytes(), latest.read_bytes()
        original_replace = comparison.os.replace

        def fail_journal(source, destination):
            if Path(destination).name == "selection-history.jsonl":
                raise OSError("simulated journal publication failure")
            return original_replace(source, destination)

        with mock.patch.object(comparison.os, "replace", side_effect=fail_journal), self.assertRaises(OSError):
            comparison.select_command(self.run, "linked", "This event must not be committed")
        self.assertEqual(history.read_bytes(), initial_history)
        self.assertEqual(latest.read_bytes(), initial_latest)
        self.assertEqual(self.cli("check", "--run", self.run)["selection_count"], 1)
        self.assertFalse((self.run / ".selection.lock").exists())

    def test_repair_refuses_corrupt_journal_and_tampered_run_evidence(self):
        self.ready()
        comparison.select_command(self.run, "interval", "Valid initial choice")
        history = self.run / "selection-history.jsonl"
        original = history.read_bytes()
        (self.run / "selection.json").unlink()
        history.write_bytes(original[:-1])
        self.cli("repair-latest", "--run", self.run, code=2)
        self.assertEqual(history.read_bytes(), original[:-1])
        self.assertFalse((self.run / "selection.json").exists())
        history.write_bytes(original)
        preview = self.run / "assets/interval/preview.png"
        preview.write_bytes(preview.read_bytes() + b"tampered")
        self.cli("repair-latest", "--run", self.run, code=2)
        self.assertFalse((self.run / "selection.json").exists())
        self.assertEqual(history.read_bytes(), original)

    def test_validation_uses_staged_copies_if_provider_changes_after_copy(self):
        self.plan()
        self.receipts()
        original_copy = comparison.copy_asset

        def mutate_after_copy(source, stage, relative):
            result = original_copy(source, stage, relative)
            if relative.endswith("preview.png"):
                source.write_bytes(png_bytes(seed=99))
            elif relative.endswith("analysis.json"):
                self.write(source, {"changed": "after the evidence copy"})
            return result

        with mock.patch.object(comparison, "copy_asset", side_effect=mutate_after_copy):
            result = comparison.assemble_command(self.run / "plan.json", self.results_file)
        self.assertTrue(result["ok"])
        self.assertTrue(comparison.check_run(self.run)[0]["ok"])

    def test_snapshot_is_independent_of_later_original_edits(self):
        self.plan()
        snapshot = self.run / self.plan_value["input_file"]
        original = snapshot.read_bytes()
        self.input.write_text("changed original after planning\n")
        self.receipts()
        self.assemble()
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertEqual(hashlib.sha256(original).hexdigest(), self.plan_value["data_sha256"])
        self.cli("check", "--run", self.run)


class PngValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "preview.png"

    def inspect(self, value):
        self.path.write_bytes(value)
        return comparison.inspect_png(self.path)

    def test_real_png_and_all_five_filter_methods_have_identical_content_digest(self):
        digests = [self.inspect(png_bytes(filter_method=method))["content_sha256"] for method in range(5)]
        self.assertEqual(len(set(digests)), 1)

    def test_rejects_truncation_crc_invalid_compression_row_filters_and_bombs(self):
        header = chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 2, 8, 2, 0, 0, 0))
        signature = b"\x89PNG\r\n\x1a\n"
        end = chunk(b"IEND", b"")
        valid = png_bytes()
        examples = [signature, valid[:-3], valid[:40] + bytes([valid[40] ^ 1]) + valid[41:],
                    signature + header + chunk(b"IDAT", b"not zlib") + end,
                    signature + header + chunk(b"IDAT", zlib.compress(b"\x00" * 50000)) + end,
                    signature + header + chunk(b"IDAT", zlib.compress(b"\x05" + b"\x00" * 9 + b"\x00" * 10)) + end,
                    signature + chunk(b"IHDR", struct.pack(">IIBBBBB", 0, 2, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"")) + end,
                    signature + chunk(b"IHDR", struct.pack(">IIBBBBB", 100000, 100000, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"")) + end,
                    valid + b"trailing", signature + header + header + chunk(b"IDAT", zlib.compress(b"\x00" * 20)) + end,
                    signature + header + chunk(b"FAKE", b"") + chunk(b"IDAT", zlib.compress(b"\x00" * 20)) + end]
        for index, value in enumerate(examples):
            with self.subTest(index=index), self.assertRaises((comparison.ComparisonError, zlib.error)):
                self.inspect(value)

    def test_subbyte_padding_is_not_counted_as_different_image_content(self):
        signature = b"\x89PNG\r\n\x1a\n"
        header = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 1, 0, 0, 0, 0))
        end = chunk(b"IEND", b"")
        first = self.inspect(signature + header + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + end)
        second = self.inspect(signature + header + chunk(b"IDAT", zlib.compress(b"\x00\x7f")) + end)
        self.assertEqual(first["content_sha256"], second["content_sha256"])

    def test_rejects_illegal_transparency_and_out_of_range_indexed_samples(self):
        signature = b"\x89PNG\r\n\x1a\n"
        rgba = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        indexed = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 3, 0, 0, 0))
        palette = chunk(b"PLTE", b"\x00\x00\x00")
        end = chunk(b"IEND", b"")
        for value in (
            signature + rgba + chunk(b"tRNS", b"\x00\x00") + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff")) + end,
            signature + indexed + chunk(b"tRNS", b"\xff") + palette + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + end,
            signature + indexed + palette + chunk(b"IDAT", zlib.compress(b"\x00\x01")) + end,
        ):
            with self.subTest(value=value), self.assertRaises(comparison.ComparisonError):
                self.inspect(value)

    def test_palette_and_transparency_lengths_prevent_false_content_collisions(self):
        signature = b"\x89PNG\r\n\x1a\n"
        header = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 4, 3, 0, 0, 0))
        data, end = chunk(b"IDAT", zlib.compress(b"\x00\x00")), chunk(b"IEND", b"")
        transparent = self.inspect(signature + header + chunk(b"PLTE", b"\x00" * 12) + chunk(b"tRNS", b"\x00\x00\x00\xff") + data + end)
        opaque = self.inspect(signature + header + chunk(b"PLTE", b"\x00" * 15) + chunk(b"tRNS", b"\xff") + data + end)
        self.assertNotEqual(transparent["content_sha256"], opaque["content_sha256"])

    def test_exact_pixels_normalize_across_all_supported_color_types_and_depths(self):
        # Two opaque pixels: black and white, represented in each legal format.
        palette = b"\x00\x00\x00\xff\xff\xff"
        cases = [(1, 0, b"\x40", b""), (2, 0, b"\x30", b""), (4, 0, b"\x0f", b""),
                 (8, 0, b"\x00\xff", b""), (16, 0, b"\x00\x00\xff\xff", b""),
                 (8, 2, b"\x00" * 3 + b"\xff" * 3, b""), (16, 2, b"\x00" * 6 + b"\xff" * 6, b""),
                 (1, 3, b"\x40", palette), (2, 3, b"\x10", palette), (4, 3, b"\x01", palette),
                 (8, 3, b"\x00\x01", palette), (8, 4, b"\x00\xff\xff\xff", b""),
                 (16, 4, b"\x00\x00\xff\xff" + b"\xff" * 4, b""),
                 (8, 6, b"\x00" * 3 + b"\xff" * 5, b""), (16, 6, b"\x00" * 6 + b"\xff" * 10, b"")]
        values = [self.inspect(sample_png(2, 1, depth, color, b"\x00" + row, colors))["content_sha256"]
                  for depth, color, row, colors in cases]
        self.assertEqual(len(set(values)), 1)

    def test_transparency_normalizes_across_palette_grayscale_rgb_and_rgba(self):
        palette = b"\x00\x00\x00\xff\xff\xff"
        values = [sample_png(2, 1, 8, 0, b"\x00\x00\xff", transparency=b"\x00\xff"),
                  sample_png(2, 1, 8, 2, b"\x00" + b"\x00" * 3 + b"\xff" * 3,
                             transparency=struct.pack(">HHH", 255, 255, 255)),
                  sample_png(2, 1, 1, 3, b"\x00\x40", palette, b"\xff\x00"),
                  sample_png(2, 1, 8, 4, b"\x00\x00\xff\xff\x00"),
                  sample_png(2, 1, 8, 6, b"\x00" + b"\x00" * 3 + b"\xff" * 4 + b"\x00")]
        self.assertEqual(len({self.inspect(value)["content_sha256"] for value in values}), 1)

    def test_sixteen_bit_precision_is_preserved(self):
        first = self.inspect(sample_png(1, 1, 16, 0, b"\x00\x12\x34"))
        second = self.inspect(sample_png(1, 1, 16, 0, b"\x00\x12\x35"))
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_adam7_and_regular_pngs_with_the_same_pixels_have_equal_digest(self):
        width, height = 9, 7
        pixel = lambda x, y: bytes([x * 17, y * 23, (x + y) * 13])
        regular = b"".join(b"\x00" + b"".join(pixel(x, y) for x in range(width)) for y in range(height))
        passes = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
        interlaced = b"".join(b"\x00" + b"".join(pixel(x, y) + b"\xff" for x in range(x0, width, dx))
                              for x0, y0, dx, dy in passes for y in range(y0, height, dy) if x0 < width)
        first = self.inspect(sample_png(width, height, 8, 2, regular))
        second = self.inspect(sample_png(width, height, 8, 6, interlaced, interlace=1))
        self.assertEqual(first["content_sha256"], second["content_sha256"])


if __name__ == "__main__":
    unittest.main()
