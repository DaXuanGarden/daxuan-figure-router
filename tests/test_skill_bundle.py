"""Isolated file-bundle installation tests; no network or real skills change."""

from __future__ import annotations

import hashlib
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.parse
import urllib.error


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "skill_bundle.py"
SPEC = importlib.util.spec_from_file_location("figure_router_skill_bundle", SCRIPT)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)
REF = "a" * 40
REPO = "example/figures"


def source_text(name):
    return f"---\nname: {name}\ndescription: fixture only\n---\n# {name}\n".encode()


class FixtureTransport:
    """A GitHub-shaped immutable tree, with no local HTTP server or network."""
    def __init__(self, files):
        self.files = dict(files)
        self.calls = []
        self.fail_paths = set()
        self.changed_bytes = {}
        self.before_fetch = None
        self.nodes = [
            {"path": path, "type": "blob", "mode": "100644", "size": len(content), "sha": bundle.git_blob(content)}
            for path, content in sorted(self.files.items())
        ]
        self.truncated = False

    def fetch(self, url, limit):
        self.calls.append(url)
        if self.before_fetch:
            self.before_fetch(url)
        if url.startswith("https://api.github.com/"):
            return json.dumps({"sha": "b" * 40, "truncated": self.truncated, "tree": self.nodes}).encode()
        prefix = f"https://raw.githubusercontent.com/{REPO}/{REF}/"
        if not url.startswith(prefix):
            raise AssertionError("unexpected or unpinned source URL: " + url)
        path = urllib.parse.unquote(url[len(prefix):])
        if path in self.fail_paths:
            raise bundle.BundleError("download_failed", "fixture download interrupted")
        return self.changed_bytes.get(path, self.files[path])


class SkillBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.target = self.base / "codex" / "skills"
        self.scan = self.base / "isolated-scan"
        self.manifest = self.base / "sources.json"
        self.files = {"LICENSE": b"MIT fixture license\n"}
        self.entries = []
        self.write_manifest()

    def public(self, name="alpha", **overrides):
        path = "skills/" + name
        self.files[path + "/SKILL.md"] = source_text(name)
        self.files[path + "/scripts/draw.py"] = b"raise RuntimeError('downloaded code must never execute')\n"
        self.files[path + "/assets/palette.json"] = b'{"fixture": true}\n'
        entry = {
            "id": name, "name": name, "target_dir": name, "status": "verified_public",
            "reason": "verified fixture", "repository": REPO, "ref": REF, "path": path,
            "skill_sha256": hashlib.sha256(self.files[path + "/SKILL.md"]).hexdigest(),
            "license": {"spdx": "MIT", "path": "LICENSE", "url": f"https://github.com/{REPO}/blob/{REF}/LICENSE"},
            "requires": [], "runtime_requirements": ["A plotting runtime is separate"], **overrides,
        }
        self.entries.append(entry)
        self.write_manifest()
        return entry

    def unavailable(self, name="private", status="unavailable", **overrides):
        entry = {"id": name, "name": name, "target_dir": name, "status": status, "reason": "No distributable public source", **overrides}
        self.entries.append(entry)
        self.write_manifest()
        return entry

    def write_manifest(self, profiles=None):
        self.manifest.write_text(json.dumps({"schema_version": 1, "skills": self.entries, "profiles": profiles or {}}), encoding="utf-8")

    def run_bundle(self, command="install", transport=None, **options):
        return bundle.execute(command, self.manifest, target=self.target, scan_roots=[self.scan],
                              transport=transport or FixtureTransport(self.files), **options)

    def snapshot(self):
        return {str(path.relative_to(self.base)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.base.rglob("*") if path.is_file()}

    def test_plan_and_status_are_offline_and_create_no_paths(self):
        self.public()
        before = self.snapshot()
        for command in ("plan", "status"):
            report = self.run_bundle(command, transport=mock.Mock(fetch=mock.Mock(side_effect=AssertionError("network forbidden"))))
            self.assertTrue(report["read_only"])
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"], {"missing": 1})
            self.assertEqual(report["downloads"], 0)
        self.assertFalse(self.target.parent.exists())
        self.assertFalse(self.scan.exists())
        self.assertEqual(before, self.snapshot())

    def test_install_complete_subtree_and_preserve_root_license_without_executing(self):
        self.public()
        self.files["skills/alpha/LICENSE"] = b"Different subtree license\n"
        self.files["skills/alpha/assets/nested/SKILL.md"] = source_text("nested-reference")
        transport = FixtureTransport(self.files)
        next(node for node in transport.nodes if node["path"].endswith("draw.py"))["mode"] = "100755"
        result = self.run_bundle(transport=transport)
        self.assertTrue(result["ok"])
        row = result["skills"][0]
        self.assertEqual(row["state"], "installed")
        self.assertTrue(row["review_required"])
        root = self.target / "alpha"
        self.assertEqual((root / "LICENSE").read_bytes(), b"Different subtree license\n")
        self.assertEqual((root / ".skill-bundle/repository/LICENSE").read_bytes(), self.files["LICENSE"])
        self.assertEqual((root / "assets/nested/SKILL.md").read_bytes(), source_text("nested-reference"))
        receipt = json.loads((root / bundle.RECEIPT).read_text())
        self.assertEqual(receipt["ref"], REF)
        self.assertEqual(len(receipt["files"]), 6)
        for relative, expected in receipt["files"].items():
            self.assertEqual(bundle.digest((root / relative).read_bytes()), expected)
        self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())
        self.assertEqual(bundle.receipt_state(root)["integrity"], "verified")

    def test_dependency_order_shared_tree_and_zero_download_zero_write_repeat(self):
        self.public("alpha", requires=["beta"])
        self.public("beta")
        transport = FixtureTransport(self.files)
        first = self.run_bundle(transport=transport, skill_ids=["alpha"])
        self.assertEqual([row["id"] for row in first["skills"]], ["beta", "alpha"])
        self.assertEqual(first["summary"], {"installed": 2})
        self.assertEqual(sum(url.startswith("https://api.github.com/") for url in transport.calls), 1)
        before = self.snapshot()
        second_transport = mock.Mock()
        second_transport.fetch.side_effect = AssertionError("repeat must be offline")
        second = self.run_bundle(transport=second_transport, skill_ids=["alpha"])
        self.assertEqual(second["summary"], {"present": 2})
        self.assertEqual(second["downloads"], 0)
        second_transport.fetch.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())

    def test_existing_identity_in_another_root_skips_custom_variant_without_overwrite(self):
        self.public()
        existing = self.scan / "different-directory" / "SKILL.md"
        existing.parent.mkdir(parents=True)
        content = source_text("alpha") + b"Locally enhanced variant\n"
        existing.write_bytes(content)
        transport = mock.Mock()
        transport.fetch.side_effect = AssertionError("existing identity must not download")
        before = self.snapshot()
        result = self.run_bundle(transport=transport)
        row = result["skills"][0]
        self.assertEqual(row["state"], "present")
        self.assertEqual(row["action"], "skip")
        self.assertTrue(row["review_required"])
        self.assertFalse(self.target.exists())
        self.assertEqual(before, self.snapshot())
        transport.fetch.assert_not_called()

    def test_modified_managed_resources_are_skipped_and_require_review(self):
        self.public()
        self.assertTrue(self.run_bundle()["ok"])
        resource = self.target / "alpha/scripts/draw.py"
        resource.write_bytes(b"# local modification\n")
        before = self.snapshot()
        second = self.run_bundle(transport=mock.Mock(fetch=mock.Mock(side_effect=AssertionError("network forbidden"))))
        self.assertEqual(second["skills"][0]["state"], "present")
        self.assertTrue(second["skills"][0]["review_required"])
        self.assertEqual(second["skills"][0]["locations"][0]["integrity"], "modified")
        self.assertEqual(before, self.snapshot())

    def test_destination_conflict_malformed_identity_and_broken_symlink_do_not_download(self):
        self.public()
        destination = self.target / "alpha"
        destination.mkdir(parents=True)
        for content in (b"# no identity\n", source_text("different-name"), b"---\nname: alpha\n"):
            (destination / "SKILL.md").write_bytes(content)
            transport = mock.Mock()
            result = self.run_bundle(transport=transport)
            self.assertFalse(result["ok"])
            self.assertEqual(result["skills"][0]["state"], "conflict")
            transport.fetch.assert_not_called()
        (destination / "SKILL.md").unlink()
        destination.rmdir()
        destination.symlink_to(self.base / "missing-destination", target_is_directory=True)
        self.assertEqual(self.run_bundle("status")["skills"][0]["state"], "conflict")
        self.assertTrue(destination.is_symlink())

    def test_unavailable_system_and_transitive_dependency_blockers_are_visible(self):
        self.public("alpha", requires=["beta"])
        self.public("beta", requires=["private"])
        self.unavailable()
        self.unavailable("system-skill", status="system")
        result = self.run_bundle()
        states = {row["id"]: row["state"] for row in result["skills"]}
        self.assertEqual(states, {"private": "unavailable", "beta": "dependency_blocked", "alpha": "dependency_blocked", "system-skill": "system"})
        self.assertEqual(result["downloads"], 0)
        self.assertFalse(result["ok"])
        self.assertFalse(self.target.exists())

    def test_non_directory_target_or_parent_is_an_offline_conflict(self):
        self.public()
        for blocked in (self.target.parent, self.target):
            with self.subTest(blocked=str(blocked)):
                blocked.parent.mkdir(parents=True, exist_ok=True)
                blocked.write_bytes(b"must remain untouched")
                transport = mock.Mock()
                result = self.run_bundle(transport=transport)
                self.assertEqual(result["skills"][0]["state"], "conflict")
                self.assertEqual(result["skills"][0]["reason"], "target_path_is_unsafe")
                self.assertEqual(blocked.read_bytes(), b"must remain untouched")
                transport.fetch.assert_not_called()
                blocked.unlink()

    def test_symlinked_target_or_parent_is_an_offline_conflict(self):
        self.public()
        real = self.base / "real-skills"
        real.mkdir()
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.symlink_to(real, target_is_directory=True)
        transport = mock.Mock()
        result = self.run_bundle(transport=transport)
        self.assertEqual(result["skills"][0]["state"], "conflict")
        self.assertEqual(result["skills"][0]["reason"], "target_path_is_unsafe")
        transport.fetch.assert_not_called()
        self.target.unlink()
        self.target.mkdir()
        parent_alias = self.base / "alias-parent"
        parent_alias.symlink_to(self.base / "real-parent", target_is_directory=True)
        target = parent_alias / "skills"
        transport = mock.Mock()
        report = bundle.execute("install", self.manifest, target=target, scan_roots=[self.scan], transport=transport)
        self.assertEqual(report["skills"][0]["reason"], "target_path_is_unsafe")
        transport.fetch.assert_not_called()

    def test_download_failure_blocks_dependents_and_leaves_no_skill_or_staging(self):
        self.public("alpha", requires=["beta"])
        self.public("beta")
        transport = FixtureTransport(self.files)
        transport.fail_paths.add("skills/beta/scripts/draw.py")
        result = self.run_bundle(transport=transport, skill_ids=["alpha"])
        self.assertEqual([row["state"] for row in result["skills"]], ["failed", "dependency_blocked"])
        self.assertEqual(result["skills"][0]["reason"], "download_failed")
        self.assertFalse((self.target / "beta").exists())
        self.assertFalse((self.target / "alpha").exists())
        self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())

    def test_wrong_git_blob_size_registry_hash_and_frontmatter_identity_are_rejected(self):
        entry = self.public()
        tests = [
            ("blob", "content_mismatch"), ("size", "content_mismatch"),
            ("hash", "skill_hash_mismatch"), ("identity", "identity_mismatch"),
        ]
        for mutation, expected in tests:
            with self.subTest(mutation=mutation):
                entry["skill_sha256"] = bundle.digest(self.files["skills/alpha/SKILL.md"])
                entry["name"] = "different" if mutation == "identity" else "alpha"
                if mutation == "hash":
                    entry["skill_sha256"] = "0" * 64
                self.write_manifest()
                transport = FixtureTransport(self.files)
                if mutation == "blob":
                    transport.changed_bytes["skills/alpha/SKILL.md"] = b"x" * len(self.files["skills/alpha/SKILL.md"])
                elif mutation == "size":
                    transport.changed_bytes["skills/alpha/SKILL.md"] = b"short"
                result = self.run_bundle(transport=transport)
                self.assertEqual(result["skills"][0]["reason"], expected)
                self.assertFalse((self.target / "alpha").exists())
                self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())

    def test_missing_root_license_and_truncated_tree_fail_before_file_download(self):
        self.public()
        for failure in ("license", "truncated"):
            with self.subTest(failure=failure):
                transport = FixtureTransport(self.files)
                if failure == "license":
                    transport.nodes = [node for node in transport.nodes if node["path"] != "LICENSE"]
                else:
                    transport.truncated = True
                result = self.run_bundle(transport=transport)
                self.assertEqual(result["skills"][0]["state"], "failed")
                self.assertEqual(len(transport.calls), 1)
                self.assertFalse(self.target.exists())

    def test_tree_symlink_submodule_traversal_and_case_collision_are_rejected(self):
        self.public()
        for mutation in ("symlink", "submodule", "traversal", "case"):
            with self.subTest(mutation=mutation):
                transport = FixtureTransport(self.files)
                node = next(item for item in transport.nodes if item["path"].endswith("draw.py"))
                if mutation == "symlink":
                    node["mode"] = "120000"
                elif mutation == "submodule":
                    node.update(mode="160000", type="commit")
                elif mutation == "traversal":
                    node["path"] = "skills/alpha/../../escape"
                else:
                    transport.nodes.append({**node, "path": "skills/alpha/scripts/DRAW.py"})
                result = self.run_bundle(transport=transport)
                self.assertEqual(result["skills"][0]["state"], "failed")
                self.assertEqual(len(transport.calls), 1)
                self.assertFalse((self.base / "escape").exists())
                self.assertFalse(self.target.exists())

    def test_limits_apply_to_declared_total_and_actual_response(self):
        self.public()
        transport = FixtureTransport(self.files)
        with mock.patch.object(bundle, "MAX_BUNDLE_BYTES", 1):
            result = self.run_bundle(transport=transport)
        self.assertEqual(result["skills"][0]["reason"], "download_limit")
        self.assertEqual(len(transport.calls), 1)
        self.assertFalse(self.target.exists())
        transport = FixtureTransport(self.files)
        transport.changed_bytes["skills/alpha/SKILL.md"] = self.files["skills/alpha/SKILL.md"] + b"extra bytes"
        result = self.run_bundle(transport=transport)
        self.assertEqual(result["skills"][0]["reason"], "content_mismatch")

    def test_concurrent_destination_creation_never_replaces_even_an_empty_directory(self):
        self.public()
        transport = FixtureTransport(self.files)
        destination = self.target / "alpha"
        def create_destination(url):
            if "/scripts/draw.py" in url:
                destination.mkdir(parents=True, exist_ok=True)
        transport.before_fetch = create_destination
        result = self.run_bundle(transport=transport)
        self.assertEqual(result["skills"][0]["state"], "conflict")
        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())

    def test_reserved_metadata_and_staging_symlink_are_refused(self):
        self.public()
        self.files["skills/alpha/.skill-bundle/receipt.json"] = b"{}"
        result = self.run_bundle()
        self.assertEqual(result["skills"][0]["reason"], "reserved_path")
        del self.files["skills/alpha/.skill-bundle/receipt.json"]
        self.target.parent.mkdir(parents=True, exist_ok=True)
        external = self.base / "elsewhere"
        external.mkdir()
        (self.target.parent / bundle.STAGING_DIR).symlink_to(external, target_is_directory=True)
        transport = FixtureTransport(self.files)
        result = self.run_bundle(transport=transport)
        self.assertEqual(result["skills"][0]["reason"], "staging_conflict")
        self.assertEqual(list(external.iterdir()), [])
        self.assertEqual(transport.calls, [])

    def test_root_skill_preserves_entire_repository_and_include_repo_files(self):
        entry = self.public()
        self.files = {"SKILL.md": source_text("alpha"), "LICENSE": b"MIT\n", "NOTICE": b"Attribution\n", "nested/resource.txt": b"resource\n"}
        entry.update(path=".", include_repo_files=["NOTICE"], skill_sha256=bundle.digest(self.files["SKILL.md"]))
        self.write_manifest()
        result = self.run_bundle()
        self.assertTrue(result["ok"])
        self.assertEqual((self.target / "alpha/NOTICE").read_bytes(), b"Attribution\n")
        self.assertFalse((self.target / "alpha/.skill-bundle/repository").exists())

    def test_manifest_rejects_mutable_refs_paths_unknown_dependencies_and_cycles(self):
        entry = self.public()
        cases = [("ref", "main"), ("path", "../escape"), ("target_dir", "../escape"),
                 ("repository", "https://github.com/example/repo"), ("skill_sha256", "short"),
                 ("include_repo_files", ["/etc/passwd"]), ("requires", ["missing"]), ("requires", ["alpha"])]
        original = dict(entry)
        for key, value in cases:
            with self.subTest(key=key, value=value):
                entry.clear()
                entry.update(original)
                entry[key] = value
                self.write_manifest()
                with self.assertRaises(bundle.BundleError):
                    self.run_bundle("plan")
                self.assertFalse(self.target.exists())

    def test_explicit_roots_isolate_discovery_and_default_roots_find_agent_project_and_codex(self):
        self.public()
        codex = self.base / "configured-codex"
        agent = self.base / "fake-home/.agents/skills"
        project = self.base / "project/.agents/skills"
        for location in (codex / "skills", agent, project):
            skill = location / "alpha/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_bytes(source_text("alpha"))
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(Path, "home", return_value=self.base / "fake-home"), mock.patch.object(Path, "cwd", return_value=self.base / "project/subdir"):
            result = bundle.execute("status", self.manifest)
            self.assertEqual(result["target"], str(codex / "skills"))
            self.assertEqual(result["skills"][0]["state"], "present")
            self.assertEqual(len(result["skills"][0]["locations"]), 3)
            isolated = self.run_bundle("status")
            self.assertEqual(isolated["skills"][0]["state"], "missing")

    def test_scan_symlink_cycles_and_installer_metadata_do_not_create_skills(self):
        self.public()
        root = self.scan / "alpha"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_bytes(source_text("alpha"))
        (root / "loop").symlink_to(self.scan, target_is_directory=True)
        for directory in (bundle.METADATA_DIR, bundle.STAGING_DIR):
            hidden = self.scan / directory
            hidden.mkdir()
            (hidden / "SKILL.md").write_bytes(source_text("hidden"))
        result = self.run_bundle("status")
        self.assertEqual(len(result["skills"][0]["locations"]), 1)
        self.assertTrue(any(item["reason"] == "symlink_cycle_skipped" for item in result["warnings"]))

    def test_profile_plus_explicit_selection_and_cli_json_error_codes(self):
        self.public("alpha")
        self.public("beta")
        self.write_manifest({"default": {"description": "small fixture", "skills": ["alpha"]}})
        self.assertEqual(self.run_bundle("plan")["requested"], ["alpha"])
        self.assertEqual(self.run_bundle("plan", profile="default", skill_ids=["beta"])["requested"], ["alpha", "beta"])
        command = [sys.executable, "-B", str(SCRIPT), "--skill", "alpha", "plan", "--skill", "beta", "--manifest", str(self.manifest), "--target", str(self.target), "--scan-root", str(self.scan)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["requested"], ["alpha", "beta"])
        result = subprocess.run(command + ["--skill", "unknown"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "unknown_skill")

    def test_identity_is_explicit_and_handles_quotes_without_directory_fallback(self):
        for text in ('---\nname: "alpha" # comment\n---\n', "---\nname: 'alpha'\n---\n", "\ufeff---\nname: alpha\n---\n"):
            self.assertEqual(bundle.skill_identity(text.encode()), "alpha")
        for text in ("name: alpha", "---\ndescription: no name\n---", "---\nname: alpha\nname: beta\n---", "---\nname: alpha\n", '---\nname: "alpha" garbage\n---'):
            with self.assertRaises(bundle.BundleError):
                bundle.skill_identity(text.encode())

    def test_pinned_blob_api_fallback_retains_all_content_and_identity_checks(self):
        self.public()
        original = self.files["skills/alpha/SKILL.md"]
        class FallbackTransport(FixtureTransport):
            corrupt = False

            def fetch(self, url, limit):
                if "/git/blobs/" in url:
                    self.calls.append(url)
                    expected = bundle.git_blob(original)
                    self.assert_expected = url.endswith(expected)
                    content = b"x" * len(original) if self.corrupt else original
                    return json.dumps({"sha": expected, "size": len(original), "encoding": "base64", "content": base64.b64encode(content).decode() + "\n"}).encode()
                if url.endswith("/alpha/SKILL.md"):
                    self.calls.append(url)
                    raise bundle.BundleError("download_failed", "raw connection timed out after 3 attempts", attempts=3, retryable=True)
                return super().fetch(url, limit)
        transport = FallbackTransport(self.files)
        result = self.run_bundle(transport=transport)
        self.assertTrue(result["ok"])
        self.assertTrue(transport.assert_expected)
        self.assertEqual((self.target / "alpha/SKILL.md").read_bytes(), original)
        # A second independent destination proves fallback bytes do not bypass
        # the same pinned tree / entry SHA-256 validation as ordinary raw bytes.
        destination = self.base / "second-target"
        transport = FallbackTransport(self.files)
        transport.corrupt = True
        result = bundle.execute("install", self.manifest, target=destination, scan_roots=[self.scan], transport=transport)
        self.assertFalse(result["ok"])
        self.assertEqual(result["skills"][0]["reason"], "content_mismatch")
        self.assertFalse((destination / "alpha").exists())

    def test_real_transport_exhaustion_reports_raw_and_blob_attempts_without_publication(self):
        self.public()
        fixture = FixtureTransport(self.files)
        tree = fixture.fetch(f"https://api.github.com/repos/{REPO}/git/trees/{REF}?recursive=1", bundle.MAX_TREE_BYTES)
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = tree
        transport = bundle.GitHubTransport()
        transport.opener = mock.Mock()
        transport.opener.open.side_effect = [response, *[TimeoutError("fixture timeout") for _ in range(6)]]
        with mock.patch.object(bundle.time, "sleep") as sleep:
            report = self.run_bundle(transport=transport)
        self.assertEqual(report["download_attempts"], 7)
        self.assertEqual(report["skills"][0]["failed_request_attempts"], 6)
        self.assertIn("pinned blob API failed", report["skills"][0]["detail"])
        self.assertEqual(sleep.call_args_list, [mock.call(1), mock.call(2), mock.call(1), mock.call(2)])
        self.assertFalse((self.target / "alpha").exists())
        self.assertFalse((self.target.parent / bundle.STAGING_DIR).exists())


class GitHubTransportRetryTests(unittest.TestCase):
    def response(self, content=b"verified bytes"):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = content
        return response

    def http_error(self, status):
        return urllib.error.HTTPError("https://raw.githubusercontent.com/example/figures/pin/file", status, "fixture", {}, None)

    def test_transient_url_timeout_429_and_5xx_retry_then_succeed(self):
        for error in (urllib.error.URLError("temporary connection failure"), TimeoutError("fixture"), self.http_error(429), self.http_error(503)):
            with self.subTest(error=type(error).__name__, status=getattr(error, "code", None)):
                transport = bundle.GitHubTransport()
                transport.opener = mock.Mock()
                response = self.response()
                transport.opener.open.side_effect = [error, TimeoutError("second attempt"), response]
                with mock.patch.object(bundle.time, "sleep") as sleep:
                    self.assertEqual(transport.fetch("https://raw.githubusercontent.com/example/figures/pin/file", 100), b"verified bytes")
                self.assertEqual(transport.attempt_count, 3)
                self.assertEqual(sleep.call_args_list, [mock.call(1), mock.call(2)])
                self.assertEqual(transport.opener.open.call_args.kwargs["timeout"], 30)
                response.__enter__.return_value.read.assert_called_once_with(101)

    def test_other_http_4xx_fail_immediately_without_sleep(self):
        for status in (400, 401, 403, 404, 410, 422):
            with self.subTest(status=status):
                transport = bundle.GitHubTransport()
                transport.opener = mock.Mock()
                transport.opener.open.side_effect = self.http_error(status)
                with mock.patch.object(bundle.time, "sleep") as sleep, self.assertRaises(bundle.BundleError) as error:
                    transport.fetch("https://raw.githubusercontent.com/example/figures/pin/file", 100)
                self.assertEqual(error.exception.attempts, 1)
                self.assertFalse(error.exception.retryable)
                self.assertEqual(transport.attempt_count, 1)
                sleep.assert_not_called()

    def test_retry_exhaustion_and_oversized_response_are_distinct(self):
        transport = bundle.GitHubTransport()
        transport.opener = mock.Mock()
        transport.opener.open.side_effect = urllib.error.URLError("fixture connection reset")
        with mock.patch.object(bundle.time, "sleep") as sleep, self.assertRaises(bundle.BundleError) as error:
            transport.fetch("https://raw.githubusercontent.com/example/figures/pin/file", 100)
        self.assertEqual(error.exception.attempts, 3)
        self.assertTrue(error.exception.retryable)
        self.assertIn("after 3 attempt", str(error.exception))
        self.assertEqual(sleep.call_count, 2)
        transport = bundle.GitHubTransport()
        transport.opener = mock.Mock()
        transport.opener.open.return_value = self.response(b"too many bytes")
        with mock.patch.object(bundle.time, "sleep") as sleep, self.assertRaises(bundle.BundleError) as error:
            transport.fetch("https://raw.githubusercontent.com/example/figures/pin/file", 2)
        self.assertEqual(error.exception.code, "download_limit")
        self.assertEqual(transport.attempt_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
