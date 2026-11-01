#!/usr/bin/env python3
"""Plan, inspect, or explicitly install pinned Skill file bundles.

Python 3.10+, standard library only. plan/status are offline and read-only.
install never executes downloaded code, installs packages, or replaces skills.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "references" / "skill-sources.json"
METADATA_DIR = ".skill-bundle"
RECEIPT = METADATA_DIR + "/receipt.json"
STAGING_DIR = ".skill-bundle-staging"
SKIP_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "__pycache__", METADATA_DIR, STAGING_DIR}
MAX_TREE_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_FILES = 6000
MAX_TREE_ENTRIES = 100000
DOWNLOAD_WORKERS = 6
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class BundleError(ValueError):
    def __init__(self, code: str, message: str, *, attempts: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.attempts = attempts
        self.retryable = retryable


def absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def repository_path(value: Any, *, allow_dot: bool = False) -> str:
    """Accept portable relative paths, never normalize away unsafe components."""
    if value == "." and allow_dot:
        return "."
    if not isinstance(value, str) or not value or value != value.strip():
        raise BundleError("invalid_path", "source paths must be nonempty relative POSIX paths")
    if value.startswith("/") or "\\" in value or any(ord(c) < 32 for c in value):
        raise BundleError("invalid_path", "absolute paths, backslashes and control characters are not allowed")
    for part in value.split("/"):
        if part in ("", ".", "..", ".git") or ":" in part or part.endswith((".", " ")):
            raise BundleError("invalid_path", "unsafe repository path component")
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise BundleError("invalid_path", "repository path is not portable to Windows")
    return value


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise BundleError("invalid_manifest", f"{label} must be a safe single-component identifier")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BundleError("invalid_manifest", "manifest is missing, unreadable, or invalid JSON") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise BundleError("invalid_manifest", "manifest schema_version must be 1")
    if not isinstance(data.get("skills"), list) or not isinstance(data.get("profiles"), dict):
        raise BundleError("invalid_manifest", "manifest needs skills array and profiles object")
    entries: dict[str, dict[str, Any]] = {}
    targets: set[str] = set()
    for item in data["skills"]:
        if not isinstance(item, dict):
            raise BundleError("invalid_manifest", "every source entry must be an object")
        source_id = identifier(item.get("id"), "id")
        identifier(item.get("name"), "name")
        target = identifier(item.get("target_dir"), "target_dir")
        if source_id in entries or target.casefold() in targets:
            raise BundleError("invalid_manifest", "source IDs and target directories must be unique")
        targets.add(target.casefold())
        if item.get("status") not in {"verified_public", "system", "unavailable"}:
            raise BundleError("invalid_manifest", f"unsupported source status for {source_id}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise BundleError("invalid_manifest", f"source reason is required for {source_id}")
        requires = item.get("requires", [])
        runtimes = item.get("runtime_requirements", [])
        if not isinstance(requires, list) or any(not isinstance(x, str) for x in requires):
            raise BundleError("invalid_manifest", f"requires must be an array of IDs for {source_id}")
        if not isinstance(runtimes, list) or any(not isinstance(x, str) for x in runtimes):
            raise BundleError("invalid_manifest", f"runtime_requirements must be an array of strings for {source_id}")
        if item["status"] == "verified_public":
            if not isinstance(item.get("repository"), str) or not REPOSITORY.fullmatch(item["repository"]):
                raise BundleError("invalid_manifest", f"repository must be GitHub owner/repo for {source_id}")
            if not isinstance(item.get("ref"), str) or not HEX40.fullmatch(item["ref"]):
                raise BundleError("invalid_manifest", f"ref must be an immutable 40-character commit for {source_id}")
            repository_path(item.get("path"), allow_dot=True)
            if not isinstance(item.get("skill_sha256"), str) or not HEX64.fullmatch(item["skill_sha256"]):
                raise BundleError("invalid_manifest", f"skill_sha256 is required for {source_id}")
            license_info = item.get("license")
            if not isinstance(license_info, dict) or not all(isinstance(license_info.get(k), str) and license_info[k] for k in ("spdx", "path", "url")):
                raise BundleError("invalid_manifest", f"license spdx/path/url is required for {source_id}")
            repository_path(license_info["path"])
            url = urllib.parse.urlsplit(license_info["url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise BundleError("invalid_manifest", f"license URL must be a plain HTTPS source URL for {source_id}")
            extra = item.get("include_repo_files", [])
            if not isinstance(extra, list):
                raise BundleError("invalid_manifest", f"include_repo_files must be an array for {source_id}")
            for file in extra:
                repository_path(file)
        entries[source_id] = item
    for name, profile in data["profiles"].items():
        identifier(name, "profile name")
        if not isinstance(profile, dict) or not isinstance(profile.get("description"), str) or not isinstance(profile.get("skills"), list):
            raise BundleError("invalid_manifest", f"profile {name} needs description and skills")
        if any(not isinstance(x, str) or x not in entries for x in profile["skills"]):
            raise BundleError("invalid_manifest", f"profile {name} references unknown source IDs")
    visited: set[str] = set()
    active: set[str] = set()

    def visit(source_id: str) -> None:
        if source_id in active:
            raise BundleError("dependency_cycle", f"dependency cycle involving {source_id}")
        if source_id in visited:
            return
        active.add(source_id)
        for dependency in entries[source_id].get("requires", []):
            if dependency not in entries:
                raise BundleError("invalid_manifest", f"unknown dependency {dependency} required by {source_id}")
            visit(dependency)
        active.remove(source_id)
        visited.add(source_id)

    for source_id in entries:
        visit(source_id)
    return data


def select_sources(manifest: dict[str, Any], profile: str | None, skill_ids: list[str] | None) -> tuple[list[str], list[str]]:
    entries = {item["id"]: item for item in manifest["skills"]}
    requested = list(skill_ids or [])
    if profile is None and not requested and "default" in manifest["profiles"]:
        profile = "default"
    if profile is not None:
        if profile not in manifest["profiles"]:
            raise BundleError("unknown_profile", f"unknown profile: {profile}")
        requested = [*manifest["profiles"][profile]["skills"], *requested]
    if not requested and profile is None:
        requested = list(entries)
    requested = list(dict.fromkeys(requested))
    for source_id in requested:
        if source_id not in entries:
            raise BundleError("unknown_skill", f"unknown source ID: {source_id}")
    ordered: list[str] = []

    def visit(source_id: str) -> None:
        if source_id in ordered:
            return
        for dependency in entries[source_id].get("requires", []):
            visit(dependency)
        ordered.append(source_id)

    for source_id in requested:
        visit(source_id)
    return ordered, requested


def default_target() -> Path:
    return absolute(Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills")


def default_roots(target: Path) -> list[Path]:
    codex = absolute(Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    roots = [target, codex / "skills", Path.home() / ".agents" / "skills"]
    for parent in [Path.cwd(), *Path.cwd().parents]:
        project = [parent / ".agents" / "skills", parent / ".codex" / "skills"]
        if any(path.is_dir() for path in project):
            roots.extend(project)
            break
    roots.append(codex / "plugins" / "cache")
    return list(dict.fromkeys(absolute(root) for root in roots))


def has_symlink_component(path: Path) -> bool:
    """Reject target aliases so an install cannot publish outside its declared root."""
    current = Path(path.anchor) if path.anchor else Path(".")
    for component in path.parts[1:] if path.anchor else path.parts:
        current /= component
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def skill_identity(content: bytes) -> str:
    """Read a real, closed frontmatter name; never infer identity from a folder."""
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeError as exc:
        raise BundleError("invalid_identity", "SKILL.md must be UTF-8") from exc
    if not lines or lines[0].strip() != "---":
        raise BundleError("invalid_identity", "SKILL.md requires closed frontmatter with an explicit name")
    end = next((i for i in range(1, min(len(lines), 256)) if lines[i].strip() == "---"), None)
    if end is None:
        raise BundleError("invalid_identity", "SKILL.md frontmatter is not closed")
    matches = [line.split(":", 1)[1].strip() for line in lines[1:end] if re.match(r"^name\s*:", line)]
    if len(matches) != 1:
        raise BundleError("invalid_identity", "SKILL.md must contain exactly one frontmatter name")
    value = matches[0]
    if value.startswith('"'):
        try:
            name, position = json.JSONDecoder().raw_decode(value)
        except ValueError as exc:
            raise BundleError("invalid_identity", "invalid quoted skill name") from exc
        tail = value[position:].strip()
        if tail and not tail.startswith("#"):
            raise BundleError("invalid_identity", "invalid content after skill name")
    elif value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if match is None:
            raise BundleError("invalid_identity", "invalid quoted skill name")
        name = match.group(1).replace("''", "'")
    else:
        name = re.sub(r"\s+#.*$", "", value).strip()
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
        raise BundleError("invalid_identity", "invalid explicit skill name")
    return name


def scan_skills(roots: list[Path]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    warnings: list[dict[str, str]] = []
    seen_paths: set[Path] = set()
    for root in roots:
        stack = [(root, frozenset())]
        while stack:
            directory, ancestors = stack.pop()
            try:
                if directory.is_file():
                    candidates = [directory] if directory.name == "SKILL.md" else []
                    children = []
                elif directory.is_dir():
                    real = directory.resolve(strict=True)
                    if real in ancestors:
                        warnings.append({"path": str(directory), "reason": "symlink_cycle_skipped"})
                        continue
                    children = sorted(directory.iterdir(), key=str)
                    candidates = [directory / "SKILL.md"] if (directory / "SKILL.md").is_file() else []
                    next_ancestors = ancestors | {real}
                    stack.extend((child, next_ancestors) for child in children if child.name not in SKIP_DIRECTORIES and child.is_dir())
                else:
                    continue
                for candidate in candidates:
                    if candidate in seen_paths:
                        continue
                    seen_paths.add(candidate)
                    if candidate.stat().st_size > MAX_FILE_BYTES:
                        warnings.append({"path": str(candidate), "reason": "skill_file_too_large"})
                        continue
                    content = candidate.read_bytes()
                    name = skill_identity(content)
                    found.setdefault(name, []).append({"path": str(candidate), "sha256": digest(content)})
            except (OSError, RuntimeError, BundleError) as exc:
                warnings.append({"path": str(directory), "reason": exc.code if isinstance(exc, BundleError) else type(exc).__name__})
    return found, warnings


def receipt_state(skill_directory: Path) -> dict[str, Any]:
    path = skill_directory / RECEIPT
    if not path.exists() and not path.is_symlink():
        return {"managed": False, "integrity": "untracked"}
    try:
        if path.is_symlink() or path.stat().st_size > MAX_TREE_BYTES:
            raise ValueError("invalid receipt")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("files"), dict) or "SKILL.md" not in data["files"]:
            raise ValueError("invalid receipt")
        for relative, expected in data["files"].items():
            repository_path(relative)
            file = skill_directory / relative
            if not isinstance(expected, str) or not HEX64.fullmatch(expected) or file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_FILE_BYTES or digest(file.read_bytes()) != expected:
                return {"managed": True, "integrity": "modified", "receipt": str(path)}
        return {"managed": True, "integrity": "verified", "receipt": str(path), "installed_ref": data.get("ref")}
    except (OSError, ValueError, BundleError):
        return {"managed": True, "integrity": "invalid_receipt", "receipt": str(path)}


def make_plan(manifest: dict[str, Any], ordered: list[str], requested: list[str], target: Path, roots: list[Path]) -> dict[str, Any]:
    installed, warnings = scan_skills(roots)
    entries = {item["id"]: item for item in manifest["skills"]}
    target_blocked = any((path.exists() or path.is_symlink()) and not path.is_dir() for path in (target, *target.parents)) or has_symlink_component(target)
    rows = []
    for source_id in ordered:
        entry = entries[source_id]
        destination = target / entry["target_dir"]
        # Explicit scan roots isolate discovery, while the destination itself is
        # always inspected to prevent replacement even when outside those roots.
        local, local_warnings = scan_skills([destination / "SKILL.md"])
        warnings.extend(local_warnings)
        locations = list(installed.get(entry["name"], []))
        known = {item["path"] for item in locations}
        locations.extend(item for item in local.get(entry["name"], []) if item["path"] not in known)
        row: dict[str, Any] = {
            "id": source_id, "name": entry["name"], "source_status": entry["status"],
            "target": str(destination), "requires": entry.get("requires", []),
            "runtime_requirements": entry.get("runtime_requirements", []), "runtime": "unverified",
            "locations": locations, "source_reason": entry["reason"],
        }
        if entry["status"] == "verified_public":
            row["source"] = {key: entry[key] for key in ("repository", "ref", "path", "skill_sha256", "license")}
        if locations:
            for location in locations:
                location.update(receipt_state(Path(location["path"]).parent))
            row.update(state="present", action="skip", reason="explicit_skill_identity_already_present", identity_verified=True)
            row["review_required"] = any(location["sha256"] != entry.get("skill_sha256", location["sha256"]) or location["integrity"] in {"modified", "invalid_receipt"} for location in locations)
            row["capability_state"] = "review_required" if row["review_required"] else "source_read_required"
        elif destination.exists() or destination.is_symlink():
            row.update(state="conflict", action="blocked", reason="destination_exists_without_matching_skill_identity")
        elif target_blocked:
            row.update(state="conflict", action="blocked", reason="target_path_is_unsafe")
        elif entry["status"] != "verified_public":
            row.update(state=entry["status"], action="blocked", reason=entry["reason"])
        else:
            row.update(state="missing", action="install", reason="verified_public_source_not_installed", review_required=True, capability_state="review_required")
        rows.append(row)
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        blockers = [source_id for source_id in row["requires"] if by_id[source_id]["state"] not in {"present", "missing"}]
        if row["state"] == "missing" and blockers:
            row.update(state="dependency_blocked", action="blocked", reason="required_skill_unavailable", blocked_by=blockers)
    report = {"schema_version": 1, "target": str(target), "scan_roots": [str(root) for root in roots], "requested": requested, "skills": rows, "warnings": warnings}
    update_summary(report)
    return report


def update_summary(report: dict[str, Any]) -> None:
    counts: dict[str, int] = {}
    for row in report["skills"]:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    report["summary"] = counts
    report["ok"] = all(row["state"] in {"present", "missing", "installed"} for row in report["skills"])


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {"api.github.com", "raw.githubusercontent.com"} or parsed.username or parsed.password:
            raise BundleError("unsafe_redirect", "GitHub download redirected outside allowed HTTPS origins")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GitHubTransport:
    """Bounded public HTTPS GETs, without credentials, package managers or hooks."""
    def __init__(self, timeout: int = 30, max_attempts: int = 3):
        if timeout <= 0 or not 1 <= max_attempts <= 3:
            raise ValueError("timeout must be positive and max_attempts must be between 1 and 3")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.opener = urllib.request.build_opener(SafeRedirect())
        self.attempt_count = 0
        self.attempt_lock = threading.Lock()

    def fetch(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "daxuan-figure-router-skill-bundle/1", "Accept": "application/vnd.github+json"})
        for attempt in range(1, self.max_attempts + 1):
            with self.attempt_lock:
                self.attempt_count += 1
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    content = response.read(limit + 1)
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                exc.close()
                if not retryable or attempt == self.max_attempts:
                    raise BundleError("download_failed", f"GitHub returned HTTP {exc.code} after {attempt} attempt(s)", attempts=attempt, retryable=retryable) from exc
            except (OSError, urllib.error.URLError, http.client.IncompleteRead) as exc:
                if attempt == self.max_attempts:
                    raise BundleError("download_failed", f"GitHub connection failed or timed out after {attempt} attempt(s)", attempts=attempt, retryable=True) from exc
            else:
                if len(content) > limit:
                    raise BundleError("download_limit", "GitHub response exceeds the download limit", attempts=attempt)
                return content
            time.sleep(attempt)  # Bounded 1s, then 2s; never retry validation errors.
        raise AssertionError("retry loop exhausted without a result")


class SourceDownloader:
    def __init__(self, transport: Any):
        self.transport = transport
        self.trees: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def tree(self, repository: str, ref: str) -> list[dict[str, Any]]:
        key = (repository, ref)
        if key not in self.trees:
            content = self.transport.fetch(f"https://api.github.com/repos/{repository}/git/trees/{ref}?recursive=1", MAX_TREE_BYTES)
            if not isinstance(content, bytes) or len(content) > MAX_TREE_BYTES:
                raise BundleError("download_limit", "GitHub tree exceeds the download limit")
            try:
                data = json.loads(content)
            except (ValueError, UnicodeError) as exc:
                raise BundleError("invalid_tree", "GitHub tree is not valid JSON") from exc
            if not isinstance(data, dict) or data.get("truncated") is not False or not isinstance(data.get("tree"), list):
                raise BundleError("incomplete_tree", "GitHub tree is missing or truncated; refusing a partial bundle")
            if len(data["tree"]) > MAX_TREE_ENTRIES:
                raise BundleError("download_limit", "GitHub tree contains too many entries")
            seen: set[str] = set()
            for item in data["tree"]:
                if not isinstance(item, dict):
                    raise BundleError("invalid_tree", "GitHub tree entry is invalid")
                path = repository_path(item.get("path"))
                if path in seen:
                    raise BundleError("invalid_tree", "GitHub tree contains duplicate paths")
                seen.add(path)
            self.trees[key] = data["tree"]
        return self.trees[key]

    def pinned_blob(self, repository: str, node: dict[str, Any]) -> bytes:
        """Fallback for a failing raw CDN, using the immutable tree's blob SHA."""
        # Include JSON and escaped newlines in GitHub's wrapped base64 content.
        limit = (((node["size"] + 2) // 3) * 4 * 11 + 9) // 10 + 8192
        content = self.transport.fetch(f"https://api.github.com/repos/{repository}/git/blobs/{node['sha']}", limit)
        if not isinstance(content, bytes) or len(content) > limit:
            raise BundleError("download_limit", "GitHub blob API response exceeds its encoded-size limit")
        try:
            data = json.loads(content)
            if not isinstance(data, dict) or data.get("sha") != node["sha"] or data.get("size") != node["size"] or data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
                raise ValueError("unexpected blob envelope")
            return base64.b64decode("".join(data["content"].split()), validate=True)
        except (ValueError, UnicodeError, binascii.Error) as exc:
            raise BundleError("invalid_blob", "GitHub blob API returned an invalid or mismatched envelope") from exc

    def populate(self, entry: dict[str, Any], payload: Path) -> dict[str, Any]:
        tree = self.tree(entry["repository"], entry["ref"])
        prefix = "" if entry["path"] == "." else entry["path"] + "/"
        extra = set(entry.get("include_repo_files", [])) | {entry["license"]["path"]}
        files: dict[str, tuple[str, dict[str, Any]]] = {}
        mapped: set[str] = set()
        found_extra: set[str] = set()
        for node in tree:
            source = node["path"]
            inside = not prefix or source.startswith(prefix)
            if not inside and source not in extra:
                continue
            if node.get("type") == "tree":
                continue
            if node.get("type") != "blob" or node.get("mode") not in {"100644", "100755"}:
                raise BundleError("unsupported_source", "selected source contains a symlink, submodule or unsupported Git entry")
            if not isinstance(node.get("sha"), str) or not HEX40.fullmatch(node["sha"]):
                raise BundleError("invalid_tree", "selected source has no valid Git blob hash")
            size = node.get("size")
            if type(size) is not int or size < 0 or size > MAX_FILE_BYTES:
                raise BundleError("download_limit", "selected source file exceeds the per-file limit")
            if source in extra:
                found_extra.add(source)
            relative = source[len(prefix):] if inside else METADATA_DIR + "/repository/" + source
            repository_path(relative)
            if inside and PurePosixPath(relative).parts[0] == METADATA_DIR:
                raise BundleError("reserved_path", "upstream source collides with installer metadata")
            if relative.casefold() in mapped:
                raise BundleError("path_collision", "source paths collide on a case-insensitive filesystem")
            mapped.add(relative.casefold())
            files[relative] = (source, node)
        if extra - found_extra:
            raise BundleError("missing_license_or_resource", "a declared repository file or license is absent from the pinned source")
        if "SKILL.md" not in files:
            raise BundleError("missing_skill", "pinned skill directory has no SKILL.md")
        if len(files) > MAX_FILES or sum(node["size"] for _, node in files.values()) > MAX_BUNDLE_BYTES:
            raise BundleError("download_limit", "selected bundle exceeds the file-count or total-byte limit")
        hashes = {}

        def fetch_file(relative: str) -> tuple[str, bytes]:
            source, node = files[relative]
            url = f"https://raw.githubusercontent.com/{entry['repository']}/{entry['ref']}/" + urllib.parse.quote(source, safe="/")
            # Declared sizes were bounded as a complete set before any downloads.
            # Six-file batches also bound outstanding response bodies in memory.
            try:
                content = self.transport.fetch(url, node["size"])
            except BundleError as raw_error:
                if raw_error.code != "download_failed" or not raw_error.retryable:
                    raise
                try:
                    content = self.pinned_blob(entry["repository"], node)
                except BundleError as fallback_error:
                    attempts = (raw_error.attempts or 0) + (fallback_error.attempts or 0)
                    raise BundleError(fallback_error.code,
                                      f"Raw download failed after {raw_error.attempts or 0} attempt(s); pinned blob API failed: {fallback_error}",
                                      attempts=attempts or None) from fallback_error
            if not isinstance(content, bytes) or len(content) != node["size"] or len(content) > MAX_FILE_BYTES:
                raise BundleError("content_mismatch", "download size does not match the pinned Git tree")
            if git_blob(content) != node["sha"]:
                raise BundleError("content_mismatch", "download Git blob hash does not match the pinned tree")
            if relative == "SKILL.md":
                if digest(content) != entry["skill_sha256"]:
                    raise BundleError("skill_hash_mismatch", "SKILL.md SHA-256 differs from the reviewed registry entry")
                if skill_identity(content) != entry["name"]:
                    raise BundleError("identity_mismatch", "SKILL.md name differs from the registered public identity")
            return relative, content

        def write_file(result: tuple[str, bytes]) -> None:
            relative, content = result
            _, node = files[relative]
            file = payload / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open("xb") as stream:
                stream.write(content)
            file.chmod(0o755 if node["mode"] == "100755" else 0o644)
            hashes[relative] = digest(content)
        write_file(fetch_file("SKILL.md"))
        remaining = sorted(path for path in files if path != "SKILL.md")
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
            for start in range(0, len(remaining), DOWNLOAD_WORKERS):
                results = list(executor.map(fetch_file, remaining[start:start + DOWNLOAD_WORKERS]))
                for result in results:
                    write_file(result)
        receipt = {
            "schema_version": 1, "source_id": entry["id"], "name": entry["name"],
            **{key: entry[key] for key in ("repository", "ref", "path", "skill_sha256", "license")},
            "include_repo_files": sorted(extra), "files": hashes,
            "installed_at": datetime.now(timezone.utc).isoformat(), "runtime": "unverified", "capability_state": "review_required",
        }
        (payload / METADATA_DIR).mkdir(exist_ok=True)
        (payload / RECEIPT).write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return receipt


def publish_new_directory(source: Path, destination: Path) -> None:
    """Atomically publish without replacing even a concurrently created folder.

    POSIX rename() can replace an empty directory. Use the operating system's
    no-replace variant through stdlib ctypes, and fail closed if unavailable.
    """
    if os.name == "nt":
        os.rename(source, destination)  # Windows rename refuses existing targets.
        return
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(library, "renameat2"):
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin" and hasattr(library, "renamex_np"):
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(destination), 4)
    else:
        raise BundleError("atomic_publish_unsupported", "this platform has no supported atomic no-replace directory rename")
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def install_one(entry: dict[str, Any], target: Path, downloader: SourceDownloader) -> dict[str, Any]:
    destination = target / entry["target_dir"]
    if destination.exists() or destination.is_symlink():
        raise BundleError("destination_conflict", "destination appeared before installation; nothing was replaced")
    staging_root = target.parent / STAGING_DIR
    created_staging = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            staging_root.mkdir(mode=0o700)
            created_staging = True
        except FileExistsError:
            if staging_root.is_symlink() or not staging_root.is_dir():
                raise BundleError("staging_conflict", "staging path is not a real directory")
        with tempfile.TemporaryDirectory(prefix="bundle-", dir=staging_root) as temporary:
            payload = Path(temporary) / "payload"
            payload.mkdir()
            receipt = downloader.populate(entry, payload)
            target.mkdir(parents=True, exist_ok=True)
            publish_new_directory(payload, destination)
        return receipt
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
            raise BundleError("destination_conflict", "destination appeared during installation; nothing was replaced") from exc
        raise BundleError("filesystem_error", "could not stage or publish the Skill bundle") from exc
    finally:
        if created_staging:
            try:
                staging_root.rmdir()
            except OSError:
                pass  # Another concurrent install may still own a staging child.


def execute(command: str, manifest_path: Path = DEFAULT_MANIFEST, *, profile: str | None = None,
            skill_ids: list[str] | None = None, target: Path | None = None,
            scan_roots: list[Path] | None = None, transport: Any = None) -> dict[str, Any]:
    if command not in {"plan", "status", "install"}:
        raise BundleError("unknown_command", "expected plan, status or install")
    manifest = load_manifest(manifest_path)
    ordered, requested = select_sources(manifest, profile, skill_ids)
    target = absolute(target) if target is not None else default_target()
    roots = [absolute(root) for root in scan_roots] if scan_roots is not None else default_roots(target)
    roots = list(dict.fromkeys(roots))
    report = make_plan(manifest, ordered, requested, target, roots)
    report.update(command=command, manifest=str(absolute(manifest_path)), read_only=command != "install", downloads=0, download_attempts=0)
    if command != "install":
        return report
    entries = {item["id"]: item for item in manifest["skills"]}
    by_id = {row["id"]: row for row in report["skills"]}
    downloader = None
    for row in report["skills"]:
        if row["state"] != "missing":
            continue
        blockers = [dependency for dependency in row["requires"] if by_id[dependency]["state"] not in {"present", "installed"}]
        if blockers:
            row.update(state="dependency_blocked", action="blocked", reason="required_skill_not_installed", blocked_by=blockers)
            continue
        # Recheck live identities before any network/write, including another
        # installer having completed a sibling source since the initial scan.
        current = make_plan(manifest, [row["id"]], [row["id"]], target, roots)["skills"][0] if not row["requires"] else None
        if current is not None and current["state"] != "missing":
            row.update(current)
            continue
        if downloader is None:
            class CountedTransport:
                def __init__(self, wrapped):
                    self.wrapped = wrapped
                    self.lock = threading.Lock()

                def fetch(self, url, limit):
                    with self.lock:
                        report["downloads"] += 1
                    return self.wrapped.fetch(url, limit)

                @property
                def attempt_count(self):
                    return getattr(self.wrapped, "attempt_count", report["downloads"])
            downloader = SourceDownloader(CountedTransport(transport if transport is not None else GitHubTransport()))
        try:
            receipt = install_one(entries[row["id"]], target, downloader)
            row.update(state="installed", action="installed", reason="verified_complete_bundle_published", identity_verified=True,
                       receipt=str(target / entries[row["id"]]["target_dir"] / RECEIPT), installed_files=len(receipt["files"]),
                       review_required=True, capability_state="review_required")
        except BundleError as exc:
            row.update(state="conflict" if exc.code == "destination_conflict" else "failed", action="blocked", reason=exc.code, detail=str(exc))
            if exc.attempts is not None:
                row["failed_request_attempts"] = exc.attempts
    report["download_attempts"] = downloader.transport.attempt_count if downloader is not None else 0
    update_summary(report)
    report["ok"] = report["ok"] and not any(row["state"] == "missing" for row in report["skills"])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "status", "install"))
    parser.add_argument("--manifest", type=Path, default=argparse.SUPPRESS)
    parser.add_argument("--profile", default=argparse.SUPPRESS)
    parser.add_argument("--skill", action="append", default=argparse.SUPPRESS)
    parser.add_argument("--target", type=Path, default=argparse.SUPPRESS)
    parser.add_argument("--scan-root", type=Path, action="append", default=argparse.SUPPRESS)
    args = vars(parser.parse_args(argv))
    try:
        report = execute(args["command"], args.get("manifest", DEFAULT_MANIFEST), profile=args.get("profile"),
                         skill_ids=args.get("skill"), target=args.get("target"), scan_roots=args.get("scan_root"))
        code = 0 if report["ok"] else 1
    except BundleError as exc:
        report = {"schema_version": 1, "ok": False, "error": exc.code, "detail": str(exc)}
        code = 2
    except OSError:
        report = {"schema_version": 1, "ok": False, "error": "filesystem_error", "detail": "could not inspect local Skill files"}
        code = 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
