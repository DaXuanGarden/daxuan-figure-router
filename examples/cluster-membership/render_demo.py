#!/usr/bin/env python3
"""Render explicitly synthetic contract data, with no statistical fitting."""
import argparse
import csv
import html
from pathlib import Path


def read(path):
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def render(destination):
    here = Path(__file__).resolve().parent
    clusters = read(here / "clusters.tsv")
    members = read(here / "plotted-members.tsv")
    traits = ["Exposure", "Trait_A", "Trait_B", "Trait_C", "Trait_D"]
    escape = html.escape
    body = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 310" role="img" aria-labelledby="title desc">',
            '<title id="title">Synthetic illustration: traceable shared clusters</title>',
            '<desc id="desc">Each row binds a candidate identifier to exact shared traits and a distinct cluster posterior. No study results.</desc>',
            '<rect width="940" height="310" fill="white"/>',
            '<g font-family="Arial, sans-serif" fill="#111111">',
            '<text x="24" y="30" font-size="18">Synthetic illustration · shared-cluster membership</text>']
    for i, row in enumerate(clusters):
        key, y = row["cluster_id"], 90 + 52 * i
        if i % 2 == 0:
            body.append(f'<rect class="reading-guide" x="20" y="{y-23}" width="900" height="46" fill="#F4F6F7"/>')
        body.append(f'<text x="190" y="{y+5}" text-anchor="end" font-size="16">{escape(row["candidate_snp"])}</text>')
        for mark in [m for m in members if m["cluster_id"] == key]:
            x = 250 + 90 * traits.index(mark["trait"])
            body.append(f'<circle class="member" data-cluster="{escape(key)}" data-trait="{escape(mark["trait"])}" cx="{x}" cy="{y}" r="6" fill="#3F6078"/>')
        pp_x = 760 + (float(row["cluster_pp"]) - .7) / .3 * 125
        body.extend([f'<line x1="760" x2="{pp_x:.3f}" y1="{y}" y2="{y}" stroke="#DBB5AF" stroke-width="2"/>',
                     f'<circle cx="{pp_x:.3f}" cy="{y}" r="5" fill="#A94B4A"/>'])
    for i, trait in enumerate(traits):
        body.append(f'<text x="{250+90*i}" y="238" font-size="14" text-anchor="middle">{escape(trait)}</text>')
    body.append('<path d="M760 218H885M760 218v5M822.5 218v5M885 218v5" fill="none" stroke="black"/>')
    for x, label in [(760, "0.70"), (822.5, "0.85"), (885, "1.00")]:
        body.append(f'<text x="{x}" y="240" font-size="13" text-anchor="middle">{label}</text>')
    body.extend(['<text x="822" y="263" font-size="14" text-anchor="middle">Cluster PP</text>',
                 '<text x="24" y="291" font-size="13">Dots: shared traits · Blank: no displayed membership · Bands: reading guides only</text>', '</g></svg>'])
    svg = "\n".join(body) + "\n"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "preview.svg").write_text(svg)
    overlays = []
    for i, row in enumerate(clusters):
        text = f'{row["candidate_snp"]}: {row["trait_set"].replace("|", ", ")} · Cluster PP {float(row["cluster_pp"]):.4f}'
        overlays.append(f'<rect class="focus-row" tabindex="0" role="button" aria-pressed="false" aria-label="{escape(text, quote=True)}" x="20" y="{67+52*i}" width="900" height="46"><title>{escape(text)}</title></rect>')
    interactive = svg.replace('</svg>', ''.join(overlays) + '</svg>')
    page = '''<!doctype html><meta charset="utf-8"><title>Synthetic shared clusters</title>
<style>body{background:#fff;color:#111;font:16px Arial;margin:24px}svg{max-width:100%;height:auto;background:white}.focus-row{fill:transparent;stroke:none;cursor:pointer}.focus-row.active{fill:#3F607810;stroke:#3F6078;stroke-width:1;outline:none}#details{min-height:3em}</style>
''' + interactive + '''<p id="details" aria-live="polite">Hover, focus or select one row. Escape clears selection. Synthetic illustration only.</p>
<script>''' + (here.parents[1] / 'scripts/cluster_reading.js').read_text() + '''</script>'''
    (destination / "preview.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    render(parser.parse_args().out)
