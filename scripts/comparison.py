#!/usr/bin/env python3
"""Collect real scientific-figure alternatives without executing plotting code.

All commands use the standard library. Plans and collected evidence are sealed
against accidental edits; these hashes are integrity receipts, not signatures
or a substitute for scientific and visual review.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import sys
import tempfile
import zlib


SCHEMA = 1
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_JSON = 16 * 1024 * 1024
MAX_PNG = 128 * 1024 * 1024
MAX_PIXELS = 64_000_000
MAX_RAW_PNG = 256 * 1024 * 1024
LANGUAGES = {"r": "R", "python": "python", "matlab": "matlab", "any": "any"}


class ComparisonError(ValueError):
    """An invalid contract or artifact, with an actionable CLI message."""


def require(condition, message):
    if not condition:
        raise ComparisonError(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def digest_file(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ComparisonError(f"Non-finite JSON number: {value}")


def read_json(path):
    require(path.is_file(), f"Missing JSON file: {path}")
    require(path.stat().st_size <= MAX_JSON, f"JSON file exceeds {MAX_JSON} bytes: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)


def object_value(value, label, nonempty=False):
    require(isinstance(value, dict) and (bool(value) or not nonempty), f"{label} must be {'a nonempty' if nonempty else 'an'} object")
    return value


def text_value(value, label, limit=4096):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit and "\x00" not in value,
            f"{label} must be nonempty text of at most {limit} characters")
    return value


def language(value):
    require(isinstance(value, str) and value.casefold() in LANGUAGES, "language must be R, python, matlab, or any")
    return LANGUAGES[value.casefold()]


def canvas(value):
    require(isinstance(value, list) and len(value) == 2, "canvas_mm must contain width and height")
    require(all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 < x <= 2000 for x in value),
            "canvas_mm dimensions must be finite, positive numbers no larger than 2000 mm")
    return [float(x) for x in value]


def source_file(value, base):
    text_value(value, "source path")
    require(not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value), "Source paths must be local files")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve(strict=True)
    require(path.is_file(), f"Source must be a regular file: {path}")
    return path


def run_file(run, value):
    """Only generated local names, never a path supplied by a gallery visitor."""
    text_value(value, "stored asset path")
    pure = PurePosixPath(value)
    require(not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts)
            and "\\" not in value and ":" not in value, f"Unsafe stored path: {value}")
    path = run.joinpath(*pure.parts)
    current = run
    for part in pure.parts:
        current = current / part
        require(not current.is_symlink(), f"Symlinked run asset is not accepted: {value}")
    require(path.resolve().is_relative_to(run.resolve()), f"Stored path escapes run: {value}")
    require(path.is_file(), f"Missing run artifact: {value}")
    return path


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def sealed(value, field):
    return {**value, field: digest_bytes(canonical(value))}


def verify_seal(value, field, label):
    object_value(value, label)
    stored = value.get(field)
    require(isinstance(stored, str) and DIGEST.fullmatch(stored), f"{label} has no valid {field}")
    unsigned = {key: item for key, item in value.items() if key != field}
    require(digest_bytes(canonical(unsigned)) == stored, f"{label} seal changed: {field}")


def validate_variants(values):
    require(isinstance(values, list) and 2 <= len(values) <= 12, "Brief requires 2–12 variants")
    ids, pairs, result = set(), set(), []
    for index, value in enumerate(values):
        object_value(value, f"variants[{index}]")
        identifier = value.get("id")
        require(isinstance(identifier, str) and SAFE_ID.fullmatch(identifier), f"Unsafe variant id: {identifier!r}")
        require(identifier not in ids, f"Duplicate variant id: {identifier}")
        ids.add(identifier)
        item = {key: text_value(value.get(key), f"{identifier}.{key}") for key in ("title", "form", "style_family", "rationale")}
        pair = (item["form"].strip().casefold(), item["style_family"].strip().casefold())
        require(pair not in pairs, f"Duplicate form/style pair: {pair}")
        pairs.add(pair)
        require("primary_skill" in value and (value["primary_skill"] is None or isinstance(value["primary_skill"], str)
                and bool(value["primary_skill"].strip())), f"{identifier}.primary_skill must be text or null")
        helpers = value.get("helpers")
        require(isinstance(helpers, list) and all(isinstance(x, str) and x.strip() for x in helpers), f"{identifier}.helpers must be a string array")
        item.update(id=identifier, primary_skill=value["primary_skill"], helpers=helpers)
        for key in ("target_context", "entry_point"):
            if key in value:
                item[key] = text_value(value[key], f"{identifier}.{key}")
        if "style_parameters" in value:
            item["style_parameters"] = object_value(value["style_parameters"], f"{identifier}.style_parameters")
        result.append(item)
    return result


def science_hash(plan):
    return digest_bytes(canonical({"data_sha256": plan["data_sha256"], "data_contract": plan["data_contract"],
                                   "analysis_sha256": plan.get("analysis_sha256")}))


def plan_command(brief_path, outdir):
    brief_path = brief_path.resolve(strict=True)
    brief = object_value(read_json(brief_path), "Brief")
    require(brief.get("schema_version") == SCHEMA, "Unsupported brief schema_version")
    title = text_value(brief.get("title"), "title")
    variants = validate_variants(brief.get("variants"))
    data_contract = object_value(brief.get("data_contract"), "data_contract", nonempty=True)
    chosen_language, size = language(brief.get("language")), canvas(brief.get("canvas_mm"))
    source = source_file(brief.get("input_file"), brief_path.parent)
    baseline = source_file(brief["analysis_file"], brief_path.parent) if brief.get("analysis_file") else None
    analysis = object_value(read_json(baseline), "analysis_file", nonempty=True) if baseline else None
    suffix = source.suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,12}", source.suffix) else ".data"
    result = {"schema_version": SCHEMA, "kind": "figure_comparison_plan", "created_at": now(),
              "title": title, "language": chosen_language, "canvas_mm": size, "data_contract": data_contract,
              "variants": variants, "input_file": "inputs/data" + suffix,
              "data_sha256": digest_file(source), "analysis_file": "inputs/analysis.json" if baseline else None,
              "analysis_sha256": digest_bytes(canonical(analysis)) if baseline else None}
    result["science_sha256"] = science_hash(result)
    result = sealed(result, "plan_sha256")
    outdir = outdir.absolute()
    require(not outdir.exists() and not outdir.is_symlink(), f"Refusing to overwrite existing run: {outdir}")
    outdir.mkdir(parents=True, exist_ok=False)
    try:
        (outdir / "inputs").mkdir()
        shutil.copyfile(source, outdir / result["input_file"])
        require(digest_file(outdir / result["input_file"]) == result["data_sha256"], "Input changed during snapshot copy")
        if baseline:
            write_new(outdir / result["analysis_file"], analysis)
        write_new(outdir / "plan.json", result)
    except Exception:
        shutil.rmtree(outdir)
        raise
    return {"ok": True, "status": "planned", "plan": str(outdir / "plan.json"), "run": str(outdir),
            "data_sha256": result["data_sha256"], "science_sha256": result["science_sha256"],
            "plan_sha256": result["plan_sha256"], "variant_count": len(variants), "rendered_count": 0}


def read_plan(path):
    require(not path.is_symlink(), "Plan must not be a symlink")
    run = path.parent.resolve(strict=True)
    value = read_json(path)
    verify_seal(value, "plan_sha256", "Plan")
    require(value.get("schema_version") == SCHEMA and value.get("kind") == "figure_comparison_plan", "Unsupported plan")
    validate_variants(value.get("variants"))
    language(value.get("language"))
    canvas(value.get("canvas_mm"))
    object_value(value.get("data_contract"), "data_contract", nonempty=True)
    require(digest_file(run_file(run, value.get("input_file"))) == value.get("data_sha256"), "Frozen input snapshot changed")
    require(science_hash(value) == value.get("science_sha256"), "Frozen scientific contract changed")
    if value.get("analysis_file"):
        analysis = object_value(read_json(run_file(run, value["analysis_file"])), "Frozen analysis", nonempty=True)
        require(digest_bytes(canonical(analysis)) == value.get("analysis_sha256"), "Frozen analysis snapshot changed")
    else:
        require(value.get("analysis_sha256") is None, "Plan analysis hash has no snapshot")
    return run, value


def _paeth(a, b, c):
    p = a + b - c
    da, db, dc = abs(p - a), abs(p - b), abs(p - c)
    return a if da <= db and da <= dc else b if db <= dc else c


def _rgba16_row(row, width, depth, color, palette, transparency):
    """Expand one reconstructed PNG row to exact big-endian RGBA16 samples."""
    if color == 3:
        indices = [((row[(pixel * depth) // 8] >> (8 - depth - (pixel * depth) % 8)) & ((1 << depth) - 1))
                   for pixel in range(width)]
        require(all(index < len(palette) for index in indices), "PNG sample index exceeds available palette")
        return b"".join(palette[index] for index in indices)
    if color == 6 and depth == 16:
        return bytes(row)
    if color == 6:
        result = bytearray(width * 8)
        result[0::2], result[1::2] = row, row
        return result
    if depth < 8:
        maximum = (1 << depth) - 1
        row = bytes((((row[(pixel * depth) // 8] >> (8 - depth - (pixel * depth) % 8)) & maximum) * 255 // maximum)
                    for pixel in range(width))
    result = bytearray(width * 8)
    step = {0: 1, 2: 3, 4: 2}[color] * (2 if depth == 16 else 1)
    # Sliced assignment keeps common RGB/RGBA previews fast without a library.
    for component in range(3):
        source = component if color == 2 else 0
        result[component * 2::8] = row[source * (2 if depth == 16 else 1)::step]
        result[component * 2 + 1::8] = row[source * 2 + 1::step] if depth == 16 else row[source::step]
    if color == 4:
        result[6::8] = row[2::step] if depth == 16 else row[1::step]
        result[7::8] = row[3::step] if depth == 16 else row[1::step]
    else:
        result[6::8] = result[7::8] = b"\xff" * width
    if transparency:
        samples = struct.unpack(">" + "H" * (len(transparency) // 2), transparency)
        transparent = b"".join(struct.pack(">H", sample * 65535 // ((1 << depth) - 1)) for sample in samples)
        for pixel in range(width):
            offset = pixel * 8
            if result[offset:offset + len(transparent)] == transparent:
                result[offset + 6:offset + 8] = b"\x00\x00"
    return result


def inspect_png(path):
    """Validate PNG chunks/CRC/zlib/scanlines; hash exact RGBA16 pixels.

    Equivalent pixels normalize across PNG colour types, bit depths, palettes,
    filters and Adam7 interlacing. Colour-profile interpretation, compositing and
    perceptual similarity are outside this exact-sample comparison.
    """
    require(path.stat().st_size <= MAX_PNG, f"PNG exceeds {MAX_PNG} bytes")
    encoded = path.read_bytes()
    require(encoded.startswith(b"\x89PNG\r\n\x1a\n"), "Preview is not a PNG")
    offset, chunks, compressed = 8, [], bytearray()
    header, palette, transparency = None, b"", b""
    saw_idat, ended_idat, saw_end = False, False, False
    while offset < len(encoded):
        require(offset + 12 <= len(encoded), "Truncated PNG chunk")
        length = struct.unpack_from(">I", encoded, offset)[0]
        kind = encoded[offset + 4:offset + 8]
        require(re.fullmatch(b"[A-Za-z]{4}", kind) is not None and 65 <= kind[2] <= 90, "Invalid PNG chunk type")
        end = offset + 12 + length
        require(end <= len(encoded), "Truncated PNG chunk payload")
        data = encoded[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", encoded, offset + 8 + length)[0]
        require(zlib.crc32(kind + data) & 0xFFFFFFFF == crc, "PNG CRC mismatch")
        require(chunks or kind == b"IHDR", "PNG must start with IHDR")
        if kind == b"IHDR":
            require(not chunks and length == 13, "Invalid or duplicate PNG IHDR")
            header = struct.unpack(">IIBBBBB", data)
        elif kind == b"PLTE":
            require(not palette and not transparency and not saw_idat and length and length % 3 == 0 and length <= 768, "Invalid PNG palette")
            palette = data
        elif kind == b"tRNS":
            require(not transparency and not saw_idat and header[3] in {0, 2, 3}, "Invalid PNG transparency order/type")
            color, depth = header[3], header[2]
            require((color == 0 and length == 2) or (color == 2 and length == 6)
                    or (color == 3 and palette and 0 < length <= len(palette) // 3), "Invalid PNG transparency length/palette")
            if color in {0, 2}:
                require(all(sample < 2 ** depth for sample in struct.unpack(">" + "H" * (length // 2), data)), "PNG transparency sample exceeds bit depth")
            transparency = data
        elif kind == b"IDAT":
            require(not ended_idat, "PNG IDAT chunks must be consecutive")
            saw_idat = True
            compressed.extend(data)
        elif kind == b"IEND":
            require(length == 0 and saw_idat and end == len(encoded), "Invalid PNG IEND or trailing content")
            saw_end = True
        elif kind[0] < 97:
            raise ComparisonError(f"Unsupported critical PNG chunk: {kind.decode('ascii')}")
        if saw_idat and kind != b"IDAT":
            ended_idat = True
        chunks.append(kind)
        offset = end
    require(header is not None and saw_end, "PNG is missing IHDR or IEND")
    width, height, depth, color, compression, filtering, interlace = header
    legal = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
    require(0 < width <= 32768 and 0 < height <= 32768 and width * height <= MAX_PIXELS, "PNG dimensions exceed supported bounds")
    require(color in legal and depth in legal[color] and compression == 0 and filtering == 0 and interlace in {0, 1}, "Invalid PNG IHDR fields")
    require(color != 3 or palette and len(palette) // 3 <= 2 ** depth, "Indexed PNG requires a valid palette")
    require(color not in {0, 4} or not palette, "Grayscale PNG must not contain a palette")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if interlace == 0 else [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    rows, expected = [], 0
    for x, y, dx, dy in passes:
        pw, ph = max(0, (width - x + dx - 1) // dx), max(0, (height - y + dy - 1) // dy)
        if pw and ph:
            rowbytes = (pw * channels * depth + 7) // 8
            rows.append((ph, rowbytes, pw, x, y, dx, dy))
            expected += ph * (rowbytes + 1)
    require(expected <= MAX_RAW_PNG, "PNG decompressed size exceeds supported bounds")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    require(len(raw) == expected and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,
            "Invalid PNG compressed stream or scanline length")
    sample_hash = hashlib.sha256(b"RGBA16-v1\x00" + struct.pack(">II", width, height))
    expanded_palette = []
    for index in range(len(palette) // 3):
        rgb = palette[index * 3:index * 3 + 3]
        alpha = transparency[index] if index < len(transparency) else 255
        expanded_palette.append(b"".join(bytes([value, value]) for value in (*rgb, alpha)))
    if interlace:
        require(width * height * 8 <= MAX_RAW_PNG, "Interlaced PNG normalized size exceeds supported bounds")
    pixels = bytearray(width * height * 8) if interlace else None
    offset, bpp = 0, max(1, (channels * depth + 7) // 8)
    for count, rowbytes, row_width, x, y, dx, dy in rows:
        previous = bytes(rowbytes)
        for row_index in range(count):
            method = raw[offset]
            require(method <= 4, "Invalid PNG scanline filter")
            row = bytearray(raw[offset + 1:offset + rowbytes + 1])
            if method:
                for j in range(rowbytes):
                    left = row[j - bpp] if j >= bpp else 0
                    above = previous[j]
                    upper_left = previous[j - bpp] if j >= bpp else 0
                    prediction = left if method == 1 else above if method == 2 else (left + above) // 2 if method == 3 else _paeth(left, above, upper_left)
                    row[j] = (row[j] + prediction) & 255
            normalized = _rgba16_row(row, row_width, depth, color, expanded_palette, transparency)
            if interlace:
                row_start = (y + row_index * dy) * width * 8
                if dx == 1:
                    pixels[row_start + x * 8:row_start + (x + row_width) * 8] = normalized
                else:
                    for pixel in range(row_width):
                        target = row_start + (x + pixel * dx) * 8
                        pixels[target:target + 8] = normalized[pixel * 8:pixel * 8 + 8]
            else:
                sample_hash.update(normalized)
            previous = row
            offset += rowbytes + 1
    if interlace:
        sample_hash.update(pixels)
    return {"width": width, "height": height, "bit_depth": depth, "color_type": color,
            "content_sha256": sample_hash.hexdigest(), "sha256": digest_bytes(encoded)}


def copy_asset(source, stage, relative):
    target = stage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    before = digest_file(source)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    require(digest_file(target) == before and digest_file(source) == before, f"Source changed while collecting: {source.name}")
    return {"path": relative, "sha256": before, "bytes": target.stat().st_size}


def prepare_variant(item, receipt, plan, base, stage):
    result = {**item, "status": receipt["status"]}
    if receipt["status"] == "blocked":
        result["reason"] = text_value(receipt.get("reason"), f"{item['id']}.reason")
        return result
    require(language(receipt.get("language")) != "any", "Rendered language must identify an actual backend")
    require(plan["language"] == "any" or language(receipt["language"]) == plan["language"], "Rendered language differs from plan")
    require(canvas(receipt.get("canvas_mm")) == plan["canvas_mm"], "Rendered canvas_mm differs from plan")
    for key in ("data_sha256", "science_sha256"):
        require(receipt.get(key) == plan[key], f"Rendered {key} differs from frozen plan")
    qa = object_value(receipt.get("qa"), "qa")
    require(qa.get("status") in {"unreviewed", "pass", "fail"}, "qa.status must be unreviewed, pass, or fail")
    if "notes" in qa:
        require(isinstance(qa["notes"], str) or isinstance(qa["notes"], list) and all(isinstance(x, str) for x in qa["notes"]), "qa.notes must be text or a text array")
    preview = source_file(receipt.get("preview"), base)
    analysis_path = source_file(receipt.get("analysis_file"), base)
    result.update(language=language(receipt["language"]), canvas_mm=canvas(receipt["canvas_mm"]),
                  data_sha256=plan["data_sha256"], science_sha256=plan["science_sha256"],
                  qa={"status": qa["status"], "notes": qa.get("notes", "")})
    prefix = "assets/" + item["id"] + "/"
    result["preview"] = copy_asset(preview, stage, prefix + "preview.png")
    result["preview"]["png"] = inspect_png(stage / result["preview"]["path"])
    result["analysis_file"] = copy_asset(analysis_path, stage, prefix + "analysis.json")
    analysis = object_value(read_json(stage / result["analysis_file"]["path"]), "Actual analysis record", nonempty=True)
    result["analysis_sha256"] = digest_bytes(canonical(analysis))
    for key, suffix in (("svg", ".svg"), ("pdf", ".pdf"), ("code", ".txt")):
        if key not in receipt:
            continue
        source = source_file(receipt[key], base)
        if key == "pdf":
            with source.open("rb") as stream:
                require(stream.read(5) == b"%PDF-", "pdf evidence is not a PDF container")
        if key == "code" and source.suffix.casefold() in {".py", ".r", ".m", ".jl", ".sh", ".ipynb"}:
            suffix = source.suffix
        result[key] = copy_asset(source, stage, prefix + key + suffix)
    if "provenance" in receipt:
        if isinstance(receipt["provenance"], str):
            result["provenance_file"] = copy_asset(source_file(receipt["provenance"], base), stage, prefix + "provenance.txt")
        else:
            result["provenance"] = object_value(receipt["provenance"], "provenance")
    evidence = qa.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    require(isinstance(evidence, list), "qa.evidence must be a file path or array of file paths")
    result["qa"]["evidence"] = [copy_asset(source_file(path, base), stage, prefix + f"qa-{index}.txt") for index, path in enumerate(evidence)]
    return result


def collection_issues(variants):
    return [f"{item['id']}: {item.get('reason', '; '.join(item.get('errors', []))) if item['status'] != 'rendered' else 'QA failed'}"
            for item in variants if item["status"] != "rendered" or item["qa"]["status"] == "fail"]


CHOICE_SCRIPT = """document.querySelectorAll('[data-choice]').forEach(function(button) {
  button.addEventListener('click', function() {
    var reason = window.prompt('Why choose this candidate for refinement?', '');
    if (reason === null) return;
    if (!reason.trim()) { window.alert('Please include a reason for the recorded choice.'); return; }
    var request = {schema_version: 1, plan_sha256: document.body.dataset.plan,
                   variant_id: button.dataset.choice, reason: reason.trim()};
    var url = URL.createObjectURL(new Blob([JSON.stringify(request, null, 2) + '\\n'], {type: 'application/json'}));
    var link = document.createElement('a'); link.href = url;
    link.download = 'choice-' + button.dataset.choice + '.json'; link.click();
    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  });
});"""


def gallery_html(plan, variants, issues):
    escape = lambda value: html.escape(str(value), quote=True)
    script_hash = base64.b64encode(hashlib.sha256(CHOICE_SCRIPT.encode()).digest()).decode()
    cards = []
    for item in variants:
        status = "Blocked" if item["status"] == "blocked" else "Invalid evidence" if item["status"] == "invalid" else {"unreviewed": "Rendered draft · QA unreviewed", "pass": "Rendered preview · QA passed", "fail": "Rendered preview · QA failed"}[item["qa"]["status"]]
        parts = [f'<article id="{item["id"]}"><h2>{escape(item["title"])}</h2>', f'<p class="status">{escape(status)}</p>',
                 f'<p><b>Form:</b> {escape(item["form"])} · <b>Style:</b> {escape(item["style_family"])}</p>',
                 f'<p>{escape(item["rationale"])}</p>', f'<p><b>Renderer:</b> {escape(item["primary_skill"] or "existing project code")}<br><b>Helpers:</b> {escape(", ".join(item["helpers"]) or "none")}</p>']
        if "preview" in item:
            preview = item["preview"]
            parts.append(f'<a href="{escape(preview["path"])}" target="_blank" rel="noopener"><img src="{escape(preview["path"])}" alt="{escape(item["title"])}" loading="lazy" width="{preview["png"]["width"]}" height="{preview["png"]["height"]}"></a>')
        if item.get("reason") or item.get("errors"):
            parts.append('<p class="problem">' + escape(item.get("reason") or "; ".join(item["errors"])) + '</p>')
        if "qa" in item:
            notes = item["qa"].get("notes", "")
            if notes:
                parts.append('<p><b>QA notes:</b> ' + escape("; ".join(notes) if isinstance(notes, list) else notes) + '</p>')
        links = [f'<a download href="{escape(item[key]["path"])}">{escape(key)}</a>' for key in ("svg", "pdf", "code", "analysis_file", "provenance_file") if key in item]
        links += [f'<a download href="{escape(asset["path"])}">QA evidence {index + 1}</a>' for index, asset in enumerate(item.get("qa", {}).get("evidence", []))]
        if links:
            parts.append('<nav aria-label="Candidate evidence">' + " · ".join(links) + '</nav>')
        if "provenance" in item:
            parts.append('<details><summary>Source evidence</summary><pre>' + escape(json.dumps(item["provenance"], ensure_ascii=False, indent=2)) + '</pre></details>')
        if item["status"] == "rendered" and item["qa"]["status"] != "fail":
            parts.append(f'<button type="button" data-choice="{item["id"]}">Export choice request</button>')
        parts.append('</article>')
        cards.append("\n".join(parts))
    state = "Partial comparison — review blocked, invalid or QA-failed candidates." if issues else "All planned candidates collected. Previews are for selection and refinement."
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{escape(plan['title'])}</title><style>
*{{box-sizing:border-box}}body{{margin:0 auto;padding:24px;max-width:1600px;background:#f4f5f7;color:#202630;font:16px/1.5 system-ui,sans-serif}}header{{max-width:1050px;margin-bottom:24px}}h1{{line-height:1.2}}h2{{font-size:1.15rem;margin-top:0}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}article{{background:#fff;border:1px solid #cdd3dd;border-radius:10px;padding:20px;min-width:0}}img{{width:100%;height:auto;display:block;background:white;margin:16px 0}}p{{overflow-wrap:anywhere}}.status{{font-weight:650}}.problem{{color:#8b1824}}button{{margin-top:16px;padding:10px 14px;cursor:pointer;border:1px solid #53647b;border-radius:5px;background:#eef2f7;color:#18283d}}nav{{display:flex;gap:10px;flex-wrap:wrap}}a{{color:#174f91}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}}code{{overflow-wrap:anywhere}}@media(max-width:850px){{body{{padding:12px}}.grid{{grid-template-columns:1fr}}article{{padding:14px}}}}
</style></head><body data-plan="{plan['plan_sha256']}"><header><h1>{escape(plan['title'])}</h1><p>{escape(state)}</p><p>Click a preview for its full size. A choice request downloads a local JSON file; it does not record a selection. Have the agent validate it with <code>comparison.py select --run RUN --choice choice-ID.json</code>. Selection is for refinement, not publication approval.</p><p><a download href="gallery.json">Evidence manifest</a> · <a download href="plan.json">Frozen plan</a></p></header><main class="grid">{''.join(cards)}</main><script>{CHOICE_SCRIPT}</script></body></html>'''


def assemble_command(plan_path, results_path):
    run, plan = read_plan(plan_path.resolve(strict=True))
    require(not any((run / name).exists() or (run / name).is_symlink() for name in ("assets", "gallery.json", "gallery.html")),
            "This run already has collected evidence; create a fresh run rather than overwrite it")
    results_path = results_path.resolve(strict=True)
    results = object_value(read_json(results_path), "Results")
    values = results.get("variants")
    require(isinstance(values, list), "Results.variants must be an array")
    receipts = {}
    for item in values:
        object_value(item, "Result row")
        identifier = item.get("id")
        require(isinstance(identifier, str) and identifier not in receipts, "Duplicate or invalid result id")
        require(item.get("status") in {"rendered", "blocked"}, f"Invalid status for {identifier}")
        receipts[identifier] = item
    require(set(receipts) == {item["id"] for item in plan["variants"]}, "Results must contain exactly one row for every planned id, with no unknown ids")
    stage = Path(tempfile.mkdtemp(prefix=".comparison-", dir=run))
    published = []
    try:
        (stage / "assets").mkdir()
        variants = []
        reference_hash = plan.get("analysis_sha256")
        for item in plan["variants"]:
            try:
                result = prepare_variant(item, receipts[item["id"]], plan, results_path.parent, stage)
                if result["status"] == "rendered":
                    if reference_hash is None:
                        reference_hash = result["analysis_sha256"]
                    require(result["analysis_sha256"] == reference_hash, "Actual analysis JSON differs from the shared scientific analysis")
                variants.append(result)
            except (OSError, ValueError, TypeError, KeyError, zlib.error) as exc:
                shutil.rmtree(stage / "assets" / item["id"], ignore_errors=True)
                variants.append({**item, "status": "invalid", "errors": [str(exc)]})
        by_content = {}
        for item in variants:
            if item["status"] == "rendered":
                by_content.setdefault(item["preview"]["png"]["content_sha256"], []).append(item)
        for duplicates in by_content.values():
            if len(duplicates) > 1:
                ids = ", ".join(item["id"] for item in duplicates)
                for item in duplicates:
                    item.update(status="invalid", errors=[f"Duplicate PNG content across variants: {ids}"])
        issues = collection_issues(variants)
        page = gallery_html(plan, variants, issues)
        (stage / "gallery.html").write_text(page, encoding="utf-8")
        gallery = sealed({"schema_version": SCHEMA, "kind": "figure_comparison_gallery", "created_at": now(),
                          "plan_sha256": plan["plan_sha256"], "data_sha256": plan["data_sha256"],
                          "science_sha256": plan["science_sha256"], "analysis_sha256": reference_hash,
                          "gallery_html_sha256": digest_file(stage / "gallery.html"), "complete": not issues,
                          "variants": variants, "issues": issues}, "gallery_sha256")
        write_new(stage / "gallery.json", gallery)
        for name in ("assets", "gallery.html", "gallery.json"):
            require(not (run / name).exists() and not (run / name).is_symlink(), f"Refusing to overwrite {name}")
            os.rename(stage / name, run / name)
            published.append(run / name)
    except Exception:
        for path in reversed(published):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"ok": not issues, "status": "assembled" if not issues else "partial", "run": str(run),
            "gallery": str(run / "gallery.html"), "manifest": str(run / "gallery.json"),
            "rendered_count": sum(x["status"] == "rendered" for x in variants), "variant_count": len(variants), "issues": issues}


def _asset_records(item):
    for key in ("preview", "analysis_file", "svg", "pdf", "code", "provenance_file"):
        if key in item:
            yield key, object_value(item[key], key)
    for asset in item.get("qa", {}).get("evidence", []):
        yield "qa evidence", object_value(asset, "qa evidence")


def read_history(run, plan, gallery):
    history_path, latest_path = run / "selection-history.jsonl", run / "selection.json"
    require(not history_path.is_symlink() and not latest_path.is_symlink(), "Selection files must not be symlinks")
    if not history_path.exists() and not latest_path.exists():
        return []
    require(history_path.is_file(), "Latest selection has no authoritative history")
    require(history_path.stat().st_size <= MAX_JSON, "Selection history exceeds supported size")
    content = history_path.read_text(encoding="utf-8")
    require(content.endswith("\n") and content.strip(), "Selection history is empty or truncated")
    events, previous = [], None
    allowed = {x["id"] for x in gallery["variants"] if x["status"] == "rendered" and x["qa"]["status"] != "fail"}
    for line in content[:-1].split("\n"):
        event = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
        verify_seal(event, "event_sha256", "Selection event")
        require(event.get("sequence") == len(events) + 1 and event.get("previous_event_sha256") == previous, "Selection history chain changed")
        require(event.get("plan_sha256") == plan["plan_sha256"] and event.get("gallery_sha256") == gallery["gallery_sha256"], "Selection history refers to a different comparison")
        require(event.get("selected_variant_id") in allowed and event.get("selection_scope") == "for_refinement", "Selection history includes an ineligible candidate")
        text_value(event.get("reason"), "Selection reason")
        previous = event["event_sha256"]
        events.append(event)
    return events


def latest_selection_status(run, events):
    """The journal is authoritative; a missing/stale latest cache is recoverable."""
    path = run / "selection.json"
    require(not path.is_symlink(), "Latest selection must not be a symlink")
    if not events:
        require(not path.exists(), "Latest selection has no authoritative history")
        return "none"
    if not path.exists():
        return "missing"
    try:
        return "current" if read_json(path) == events[-1] else "stale"
    except (OSError, ValueError, TypeError, RecursionError):
        return "stale"


def check_run(run, include_history=True):
    run = run.resolve(strict=True)
    _, plan = read_plan(run / "plan.json")
    gallery = read_json(run_file(run, "gallery.json"))
    verify_seal(gallery, "gallery_sha256", "Gallery")
    require(gallery.get("schema_version") == SCHEMA and gallery.get("kind") == "figure_comparison_gallery", "Unsupported gallery")
    for key in ("plan_sha256", "data_sha256", "science_sha256"):
        require(gallery.get(key) == plan[key], f"Gallery {key} differs from plan")
    require(digest_file(run_file(run, "gallery.html")) == gallery.get("gallery_html_sha256"), "Gallery HTML changed")
    values = gallery.get("variants")
    require(isinstance(values, list) and [x.get("id") for x in values] == [x["id"] for x in plan["variants"]], "Gallery variant set/order differs from plan")
    content_seen = set()
    for item, planned in zip(values, plan["variants"]):
        require(all(item.get(key) == value for key, value in planned.items()), f"Gallery variant configuration changed: {planned['id']}")
        require(item.get("status") in {"rendered", "blocked", "invalid"}, "Invalid gallery variant status")
        for key, asset in _asset_records(item):
            file = run_file(run, asset.get("path"))
            require(file.stat().st_size == asset.get("bytes") and digest_file(file) == asset.get("sha256"), f"Collected {key} changed: {item['id']}")
            if key == "preview":
                require(inspect_png(file) == asset.get("png"), f"Collected PNG receipt changed: {item['id']}")
            if key == "analysis_file":
                actual = object_value(read_json(file), "Collected analysis", nonempty=True)
                require(digest_bytes(canonical(actual)) == item.get("analysis_sha256"), f"Collected analysis changed: {item['id']}")
        if item["status"] == "rendered":
            require("preview" in item and "analysis_file" in item and item.get("qa", {}).get("status") in {"unreviewed", "pass", "fail"}, "Rendered candidate lacks evidence")
            require(item.get("data_sha256") == plan["data_sha256"] and item.get("science_sha256") == plan["science_sha256"], "Rendered candidate scientific receipt changed")
            require(canvas(item.get("canvas_mm")) == plan["canvas_mm"] and (plan["language"] == "any" or language(item.get("language")) == plan["language"]), "Rendered candidate language/canvas changed")
            require(item["analysis_sha256"] == gallery.get("analysis_sha256") and (plan.get("analysis_sha256") is None or item["analysis_sha256"] == plan["analysis_sha256"]), "Analysis no longer matches frozen/shared analysis")
            content = item["preview"]["png"]["content_sha256"]
            require(content not in content_seen, "Gallery counts duplicate PNG content as rendered")
            content_seen.add(content)
        elif item["status"] == "blocked":
            text_value(item.get("reason"), "Blocked reason")
        else:
            require(isinstance(item.get("errors"), list) and bool(item["errors"]), "Invalid candidate requires errors")
    issues = collection_issues(values)
    require(gallery.get("complete") == (not issues) and gallery.get("issues") == issues, "Gallery completion state changed")
    events = read_history(run, plan, gallery) if include_history else []
    latest_status = latest_selection_status(run, events) if include_history else "not_checked"
    if latest_status in {"missing", "stale"}:
        issues = [*issues, f"Latest selection cache is {latest_status}; authoritative history is valid. Run repair-latest --run RUN."]
    return {"ok": not issues, "status": "selection_cache_stale" if latest_status in {"missing", "stale"} else "verified" if not issues else "partial", "run": str(run), "issues": issues,
            "rendered_count": sum(x["status"] == "rendered" for x in values), "variant_count": len(values),
            "selection_count": len(events), "latest_selection_status": latest_status,
            "selected_variant_id": events[-1]["selected_variant_id"] if events else None}, plan, gallery, events


def selection_lock(run):
    lock = run / ".selection.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ComparisonError("Another selection is in progress; inspect .selection.lock if an earlier process was interrupted") from exc
    os.close(descriptor)
    return lock


def stage_latest(run, event):
    descriptor, name = tempfile.mkstemp(prefix=".selection-", suffix=".json", dir=run)
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(event, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def repair_latest_command(run):
    summary, _, _, events = check_run(run)
    run = Path(summary["run"])
    if summary["latest_selection_status"] in {"none", "current"}:
        return {**summary, "status": "latest_already_current", "action_success": True}
    lock, temporary = selection_lock(run), None
    try:
        # Revalidate all run evidence and the complete journal while locked.
        summary, _, _, events = check_run(run)
        require(events, "Cannot repair latest without an authoritative selection event")
        temporary = stage_latest(run, events[-1])
        os.replace(temporary, run / "selection.json")
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()
    checked = check_run(run)[0]
    return {**checked, "status": "latest_repaired" if checked["ok"] else "latest_repaired_partial", "action_success": True}


def select_command(run, identifier=None, reason=None, choice_path=None):
    summary, plan, gallery, _ = check_run(run)
    run = Path(summary["run"])
    require(summary["latest_selection_status"] in {"none", "current"}, "Latest selection cache needs repair-latest before another selection")
    if choice_path:
        request = object_value(read_json(choice_path.resolve(strict=True)), "Choice request")
        require(request.get("schema_version") == SCHEMA and request.get("plan_sha256") == plan["plan_sha256"], "Choice request belongs to a different plan")
        require(identifier is None and reason is None, "Use either --choice or --id/--reason")
        identifier, reason = request.get("variant_id"), request.get("reason")
    text_value(reason, "Selection reason")
    matches = [item for item in gallery["variants"] if item["id"] == identifier]
    require(matches and matches[0]["status"] == "rendered" and matches[0]["qa"]["status"] != "fail", "Candidate is unknown, blocked, invalid, or failed QA")
    lock = selection_lock(run)
    temporary, journal_temporary, cache_error = None, None, None
    try:
        summary, plan, gallery, events = check_run(run)
        require(summary["latest_selection_status"] in {"none", "current"}, "Latest selection cache needs repair-latest before another selection")
        event = sealed({"schema_version": SCHEMA, "sequence": len(events) + 1, "selected_at": now(),
                        "selected_variant_id": identifier, "reason": reason.strip(), "selection_scope": "for_refinement",
                        "plan_sha256": plan["plan_sha256"], "gallery_sha256": gallery["gallery_sha256"],
                        "previous_event_sha256": events[-1]["event_sha256"] if events else None}, "event_sha256")
        temporary = stage_latest(run, event)
        fd, name = tempfile.mkstemp(prefix=".selection-history-", suffix=".jsonl", dir=run)
        journal_temporary = Path(name)
        # Atomic copy-on-write publication preserves every committed event and
        # avoids leaving a partially appended JSON line after disk/write failure.
        with os.fdopen(fd, "wb") as stream:
            history = run / "selection-history.jsonl"
            if events:
                with history.open("rb") as previous:
                    shutil.copyfileobj(previous, stream)
            stream.write(canonical(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(journal_temporary, run / "selection-history.jsonl")
        journal_temporary = None  # The event is now committed to the journal.
        try:
            os.replace(temporary, run / "selection.json")
            temporary = None
        except OSError as exc:
            cache_error = str(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if journal_temporary is not None:
            journal_temporary.unlink(missing_ok=True)
        lock.unlink()
    if cache_error is not None:
        return {"ok": False, "action_success": False, "selection_committed": True,
                "status": "selection_committed_latest_stale", "selected_variant_id": identifier,
                "selection_count": event["sequence"], "selection_scope": "for_refinement",
                "history": str(run / "selection-history.jsonl"), "issues": [cache_error],
                "recovery": "Run repair-latest --run RUN; do not repeat the committed selection."}
    return {"ok": summary["ok"], "action_success": True, "status": "selected" if summary["ok"] else "selected_partial",
            "selection_committed": True,
            "selected_variant_id": identifier, "selection_scope": "for_refinement", "selection_count": event["sequence"],
            "selection": str(run / "selection.json"), "history": str(run / "selection-history.jsonl"), "issues": summary["issues"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser("plan", help="Freeze a brief and input in a fresh run")
    planning.add_argument("--brief", required=True, type=Path)
    planning.add_argument("--outdir", required=True, type=Path)
    collecting = commands.add_parser("assemble", help="Validate and collect real outputs into an offline gallery")
    collecting.add_argument("--plan", required=True, type=Path)
    collecting.add_argument("--results", required=True, type=Path)
    checking = commands.add_parser("check", help="Recheck frozen contracts, collected assets and selection history")
    checking.add_argument("--run", required=True, type=Path)
    repairing = commands.add_parser("repair-latest", help="Rebuild only a stale latest cache from a fully verified selection journal")
    repairing.add_argument("--run", required=True, type=Path)
    selecting = commands.add_parser("select", help="Append a validated author choice for refinement")
    selecting.add_argument("--run", required=True, type=Path)
    selecting.add_argument("--id")
    selecting.add_argument("--reason")
    selecting.add_argument("--choice", type=Path, help="Import a choice request exported by gallery.html")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_command(args.brief, args.outdir)
        elif args.command == "assemble":
            result = assemble_command(args.plan, args.results)
        elif args.command == "check":
            result = check_run(args.run)[0]
        elif args.command == "repair-latest":
            result = repair_latest_command(args.run)
        else:
            result = select_command(args.run, args.id, args.reason, args.choice)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError, zlib.error) as exc:
        print(json.dumps({"ok": False, "status": "error", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
