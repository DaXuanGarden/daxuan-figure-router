#!/usr/bin/env python3
"""Render four real candidates via installed skills, then collect them.

This example adapter is deliberately limited to the supplied synthetic forest
results. It is not a renderer added to the router's general CLI. No fitting,
package installation, or network access occurs here. Read the selected skills
and their entry contracts before using a different version or dataset.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cli(*args):
    completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/comparison.py"), *map(str, args)], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path, required=True, help="Explicit reviewed root with make-sci-data-figures and sci-color-palettes")
    parser.add_argument("--outdir", type=Path, required=True, help="Fresh output directory, never overwrite")
    parser.add_argument("--allow-reviewed-local", action="store_true", help="Use an explicitly reviewed local installation; output records that public bootstrap was not proven")
    args = parser.parse_args()
    root = args.skills_root.resolve()
    out = args.outdir.resolve()
    if out.exists():
        parser.error("outdir already exists; choose a fresh directory")
    provider = root / "make-sci-data-figures"
    palette_skill = root / "sci-color-palettes"
    paths = [provider / "scripts/advanced_template_workbench.py", provider / "scripts/data_family_workbench.py", provider / "scripts/figure_workbench.py", palette_skill / "scripts/sci_palettes/core.py"]
    for path in paths:
        if not path.is_file():
            parser.error(f"missing reviewed provider entry: {path}")
    # Do not pretend any same-name source is the tested public implementation.
    lock = json.loads((ROOT / "references/skill-sources.json").read_text())
    sources = {s['id']: s for s in lock['skills']}
    for sid, directory in [("make-sci-data-figures", provider), ("sci-color-palettes", palette_skill)]:
        expected = sources[sid]
        if sha(directory / "SKILL.md") != expected['skill_sha256'] and not args.allow_reviewed_local:
            parser.error(f"{sid}: source differs from demo's pinned public contract; review/adapt explicitly")
        receipt_path = directory / '.skill-bundle/receipt.json'
        if not receipt_path.is_file() and not args.allow_reviewed_local:
            parser.error(f"{sid}: use the pinned skill_bundle installer for this demo")
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text())
            if any(receipt.get(key) != expected[key] for key in ['repository','ref','path','skill_sha256']):
                parser.error(f"{sid}: receipt does not match the pinned source")
            for relative, expected_hash in receipt['files'].items():
                file = (directory / relative).resolve()
                if not file.is_relative_to(directory) or not file.is_file() or sha(file) != expected_hash:
                    parser.error(f"{sid}: installed source changed: {relative}")
    out.mkdir(parents=True)
    # Keep matplotlib's import-time caches inside the run, not third-party skills.
    os.environ['MPLCONFIGDIR'] = str(out / 'mpl-cache')
    sys.path[:0] = [str(provider / "scripts"), str(palette_skill / "scripts")]
    advanced = importlib.import_module("advanced_template_workbench")
    palettes = importlib.import_module("sci_palettes")
    import matplotlib
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import numpy as np
    import pandas as pd
    from PIL import Image, ImageDraw, ImageFont

    rows = list(csv.DictReader((Path(__file__).parent / "accepted-results.csv").open()))
    groups = list(dict.fromkeys(row['group'] for row in rows))
    variants = []
    forms = [("intervals", "forest_intervals", "Intervals", "Prioritize estimates and their supplied confidence intervals."),
             ("linked", "forest_reference_linked", "Reference-linked intervals", "Emphasize distance from the common reference without hiding uncertainty.")]
    styles = [("glacier", "Air / cool", "Open white space and round markers for a compact main-text figure."),
              ("burgundy", "Structured / warm", "Subtle row guides and square markers for denser result reading.")]
    for style_id, style_title, style_reason in styles:
        for short, stem, title, rationale in forms:
            variants.append(dict(id=f"{short}-{style_id}", title=f"{title} · {style_title}", form=stem,
                                 style_family=style_id, rationale=rationale + ' ' + style_reason,
                                 primary_skill="make-sci-data-figures", helpers=["sci-color-palettes"],
                                 entry_point="scripts/advanced_template_workbench.py:forest",
                                 style_parameters=dict(palette=f"sci-color-palettes:{style_id}", row_guides=style_id == 'burgundy', font="DejaVu Sans")))
    brief = dict(schema_version=1, title="One accepted result table · four visual alternatives (synthetic)",
                 input_file=str(Path(__file__).parent / "accepted-results.csv"), language="python", canvas_mm=[121.92,91.44],
                 data_contract=dict(input_state="accepted_results", experimental_unit="Five synthetic accepted model result rows, not raw observations",
                                    interval="Supplied illustrative 95% confidence intervals", analysis_effect="render_only",
                                    inclusion="All five supplied rows; no filtering", order=[r['term'] for r in rows],
                                    scale="linear", xlim=[0.5,1.65], reference=1.0, units="effect ratio",
                                    group_mapping=groups, note="Synthetic demonstration, no research conclusion or new inference"), variants=variants)
    brief_path = out / 'brief.json'
    write_json(brief_path, brief)
    run = out / 'run'
    cli('plan', '--brief', brief_path, '--outdir', run)
    plan = json.loads((run / 'plan.json').read_text())
    snapshot = run / plan['input_file']
    source_record = dict(renderer="make-sci-data-figures", palette_helper="sci-color-palettes",
                         repositories={sid:{k:sources[sid][k] for k in ['repository','ref','path','skill_sha256']} for sid in ['make-sci-data-figures','sci-color-palettes']},
                         entry_sha256={p.name:sha(p) for p in paths}, adapter_sha256=sha(__file__),
                         runtime={"python":sys.version.split()[0],"matplotlib":matplotlib.__version__,"numpy":np.__version__,"pandas":pd.__version__},
                         scope="One real drawing skill, one real palette skill; two forest forms and two styles. No model fit.",
                         source_verification="local reviewed installation; public pinned bootstrap must be proven separately" if args.allow_reviewed_local else "pinned public bootstrap receipt verified")
    results = []
    observed = []
    original_save = advanced._save_bundle
    for style_id, _, _ in styles:
        # The helper supplies colours only; its global theme is not applied.
        colors = palettes.select(palettes.palette(style_id), len(groups))
        color_map = dict(zip(groups, colors))
        target = out / style_id
        evidence = []
        def save_comparable(directory, figures, profile, analysis, recipe):
            for stem, fig in figures:
                ax = fig.axes[0]
                ax.set_xlim(0.5, 1.65)
                ax.set_ylim(-0.5, len(rows) - 0.5)
                ax.set_xticks([0.6,0.8,1.0,1.2,1.4,1.6])
                ax.set_xlabel('Supplied effect ratio (95% CI)')
                fig.subplots_adjust(left=0.36, right=0.96, bottom=0.19, top=0.89)
                if style_id == 'burgundy':
                    for index in range(len(rows)):
                        if index % 2 == 0:
                            ax.axhspan(index-0.45,index+0.45,color='#F3F0EE',zorder=0)
                    for container in ax.containers:
                        if hasattr(container, 'lines'):
                            container.lines[0].set_marker('s')
                handles = [Line2D([],[],color=color_map[g],marker='s' if style_id=='burgundy' else 'o',linestyle='None',label=g,markersize=4) for g in groups]
                fig.legend(handles=handles,loc='upper right',bbox_to_anchor=(0.97,0.995),frameon=False,ncol=2,fontsize=8)
                # Observe actual artists before export, not merely requested options.
                plotted = []
                for container in ax.containers:
                    if not hasattr(container, 'lines'):
                        continue
                    point, _, bars = container.lines
                    segment = bars[0].get_segments()[0]
                    plotted.append(dict(estimate=float(point.get_xdata()[0]), y=float(point.get_ydata()[0]),
                                        lower=float(segment[0][0]), upper=float(segment[1][0]),color=mcolors.to_hex(point.get_color())))
                expected = list(reversed(rows))
                if len(plotted) != len(expected):
                    raise ValueError('renderer changed number of accepted result marks')
                for index,(actual,row) in enumerate(zip(plotted,expected)):
                    wanted = [float(row['estimate']),float(row['lower']),float(row['upper']),float(index)]
                    if not np.allclose([actual['estimate'],actual['lower'],actual['upper'],actual['y']],wanted,rtol=0,atol=1e-12):
                        raise ValueError('renderer changed supplied result coordinates')
                    if actual['color'].lower()!=color_map[row['group']].lower():
                        raise ValueError('renderer changed category colour mapping')
                evidence.append(dict(stem=stem,xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim()),axes_bounds=list(ax.get_position().bounds),
                                     canvas_mm=list(fig.get_size_inches()*25.4),font=profile.get('font'),group_color_map=color_map,plotted=plotted,
                                     numeric_review="pass: actual artists equal all supplied estimates and intervals",
                                     visual_review="unreviewed: requires inspection of exported figures"))
            recipe['comparison_adapter'] = dict(xlim=[0.5,1.65],style=style_id,group_color_map=color_map,source=source_record)
            return original_save(directory,figures,profile,analysis,recipe)
        advanced._save_bundle = save_comparable
        try:
            advanced.forest(snapshot,'term','estimate','lower','upper',target,group='group',scale='linear',reference=1.0,
                            colors_text=','.join(colors),font='DejaVu Sans')
        finally:
            advanced._save_bundle = original_save
            plt.close('all')
        observed.extend(evidence)
        ev_path = target / 'observed-artists.json'
        write_json(ev_path,evidence)
        for short,stem,_,_ in forms:
            results.append(dict(id=f'{short}-{style_id}',status='rendered',preview=str(target/f'{stem}.png'),
                                svg=str(target/f'{stem}.svg'),pdf=str(target/f'{stem}.pdf'),code=str(Path(__file__).resolve()),
                                language='python',canvas_mm=[121.92,91.44],data_sha256=plan['data_sha256'],science_sha256=plan['science_sha256'],
                                analysis_file=str(target/'analysis_plan.json'),provenance=source_record,
                                qa=dict(status='unreviewed',notes='Numerical artist checks passed; visual/final QA still required.',evidence=[str(ev_path)])))
    # Same result coordinates and geometry across every exported candidate.
    for key in ['xlim','ylim','axes_bounds','canvas_mm']:
        if not all(np.allclose(observed[0][key],row[key],rtol=0,atol=1e-10) for row in observed):
            raise ValueError(f'inconsistent comparison geometry: {key}')
    write_json(out/'results.json',dict(variants=results))
    cli('assemble','--plan',run/'plan.json','--results',out/'results.json')
    cli('check','--run',run)
    # Overview labels are outside the reusable artwork. Full-size images stay linked.
    thumb_w,thumb_h=800,600
    sheet=Image.new('RGB',(1660,1430),'#F6F7F9');draw=ImageDraw.Draw(sheet)
    font_path=matplotlib.font_manager.findfont('DejaVu Sans')
    title_font=ImageFont.truetype(font_path,28);small_font=ImageFont.truetype(font_path,21)
    draw.text((30,20),'ONE DATASET / FOUR REAL CANDIDATES',fill='#172C3C',font=title_font)
    draw.text((30,62),'Synthetic accepted results. Same values, axes and canvas. Choose a direction.',fill='#425565',font=small_font)
    for index,row in enumerate(results):
        x=20+(index%2)*820;y=110+(index//2)*650
        draw.text((x+10,y),row['id'],fill='#172C3C',font=small_font)
        with Image.open(row['preview']) as im:
            im=im.convert('RGB');im.thumbnail((thumb_w,thumb_h));sheet.paste(im,(x,y+35))
    sheet.save(out/'contact-sheet.png')
    print(json.dumps(dict(status='rendered_drafts',variants=len(results),forms=2,styles=2,run=str(run),gallery=str(run/'gallery.html'),contact_sheet=str(out/'contact-sheet.png'),selection='none; author preference is not inferred'),indent=2))


if __name__=='__main__':
    main()
