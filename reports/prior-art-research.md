# Prior-Art Research

- Researched at: 2026-11-08
- Queries: `scientific figure router agent skill`; `GWAS visualization skill`; `figure quality evaluation skill`; `reproducible scientific plotting workflow`
- Catalogs: skills.sh and SkillsMP through the bundled Qiaomu runner; GitHub source review for shortlisted projects
- Rating evidence: unavailable; skills.sh installs and SkillsMP repository stars remain separate metrics
- Runner artifact: `prior-art-candidates.json`

## Discovery status

The unified runner completed the first query and returned both catalogs for several queries. Some
skills.sh requests returned no parseable candidates for the GWAS and reproducible-plotting queries;
this is recorded as missing evidence. The comparison below therefore uses source-level GitHub review
and does not claim a complete ecosystem ranking.

| Candidate | Role | Source | Mechanism retained or assessed | Metrics |
|---|---|---|---|---|
| scientific-figure-skills | direct lifecycle anchor | https://github.com/enesgul23/scientific-figure-skills | intake → design → render → audit → package and project memory | rating evidence unavailable |
| Scientific-figures-skillset | integrity/trust anchor | https://github.com/kilickursat/Scientific-figures-skillset | vector-first output, manifest, strict QC and evidence boundary | rating evidence unavailable |
| academic-figure-skill | publication QA anchor | https://github.com/TingxiYu/academic-figure-skill | fixed physical size, multi-format export and repeated QA | rating evidence unavailable |
| sci-figure | lightweight planning anchor | https://github.com/xiao-yuling/sci-figure | figure contract, editable SVG/PDF and intent-to-output workflow | rating evidence unavailable |
| K-Dense scientific visualization | semantic-method anchor | https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/docs/skill-guides/scientific-visualization.md | variable semantics, missingness, uncertainty and truthful encoding | rating evidence unavailable |
| ggwas | GWAS plot specialist | https://github.com/bczech/ggwas | Manhattan, circular GWAS, regional and gene-track primitives | repository attention is not a quality score |
| scientific-plotting-skill | low-friction plotting | https://github.com/dazhiyang/scientific-plotting-skill | small default surface, PDF-first and stable dimensions | rating evidence unavailable |
| agentfiguregallery | reference-gallery specialist | https://github.com/dsadd4/agentfiguregallery | visual inspiration and comparison gallery | reference only; no source renderer assumed |

## Synthesis ledger

### Keep

- lifecycle routing and project memory from `scientific-figure-skills`;
- evidence-bound manifests and deterministic QC from `Scientific-figures-skillset`;
- physical output contracts and repeated QA from `academic-figure-skill`;
- GWAS-specific plot primitives from `ggwas`;
- semantic and uncertainty checks from K-Dense.

### Adapt

- convert general figure contracts into the project-specific `FigureBrief` and six display-only GWAS recipes;
- keep visual reference images as structure/style evidence only, never as data or threshold sources;
- use append-only selection history instead of autonomous skill self-editing;
- keep the router backend-neutral while preserving the user-selected R/Python code.

### Reject

- treating repository stars or catalog installs as user ratings or correctness evidence;
- copying journal tokens or default colors without the target journal and data contract;
- using a generic plot template to refit GWAS/MR/coloc statistics;
- assuming nearest-gene annotations are causal genes;
- auto-executing remote scripts or auto-pushing a default Git branch.

### Invent

- a LST–CVD FigureBrief tying global correlation, PLACO+, coloc and ANNOVAR evidence to permitted claims;
- GWAS recipes that separate trait-pair, locus, annotation and causal-language layers;
- a two-level validation model: portable contract tests plus explicit missing evidence for live render/human review;
- bounded visual memory that can learn label, spacing and palette preferences without changing statistical results.

## Evidence labels

- **Design advantage:** the package explicitly separates scientific evidence contracts from visual candidate selection.
- **Validated advantage:** 94 unit tests and 121 subtests pass; the current project FigureBrief resolves 5 real input records and 6 candidates with `--check-paths`.
- **Hypothesis:** the GWAS recipes should reduce repeated routing errors and improve figure iteration speed; comparative provider-backed rendering and blind human review remain missing evidence.
