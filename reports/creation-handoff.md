# Creation Handoff — daxuan-figure-router 0.2.1

## 1. Result

- **Skill:** `daxuan-figure-router` 0.2.1
- **Job:** 将科研绘图意图、已验收结果、参考图和作者偏好路由到可比较且可审计的图形候选，同时保留语言、代码和统计证据边界。
- **Local path:** `/home/daxuan/.codex/skills/daxuan-figure-router`
- **Publication status:** `v0.2.0` is published at the GitHub remote; `v0.2.1` contains the Daxuan author/profile correction and is pending a separate release.

## 2. Reference skills studied

- `scientific-figure-skills`: adopted lifecycle routing and project memory in `SKILL.md`, `FigureBrief` and comparison records.
- `Scientific-figures-skillset`: adapted evidence-bound manifest and output-QC ideas in `gwas-figure-recipes.md` and `FigureBrief`.
- `academic-figure-skill`: adapted fixed physical output and multi-pass QA requirements in the output contract.
- `ggwas`: adapted the separation of global, regional, circular GWAS and gene-level display recipes without importing its analysis defaults.

## 3. Absorbed and rejected

- **Keep:** lifecycle routing, evidence manifests, fixed output contracts, GWAS-specific visual primitives.
- **Adapt:** general figure contracts become LST–CVD-specific, display-only recipes; memory is append-only and human-approved.
- **Reject:** generic templates that refit statistics, automatic causal interpretation, unreviewed remote execution, and popularity-as-quality claims.
- **Invent:** a `FigureBrief` that records PLACO+/coloc/ANNOVAR evidence boundaries and a bounded comparison workflow for the project's circular dendrogram, heatmap, regional plot and forest plot.

## 4. Advantages and highlights

| Label | Statement | Evidence |
|---|---|---|
| design advantage | The router separates figure form, evidence layer and causal-language level. | `references/gwas-figure-recipes.json` |
| design advantage | The same accepted result can produce rectangular, circular, regional and forest candidates without changing upstream statistics. | `references/gwas-figure-recipes.md` |
| validated advantage | Portable contract and regression checks pass. | 94 tests, 121 subtests |
| validated advantage | The real LST–CVD brief resolves all declared input paths when `--check-paths` is enabled. | `FIGURE_BRIEF_LST_CVD_20261107.json` |
| hypothesis | Candidate comparison and bounded visual memory will shorten figure iteration and reduce label/legend regressions. | Live renderer comparison and blind human review are missing evidence |

## 5. Verification and limits

- `validate_skill.py`: package validation is available after the Qiaomu evidence files are present.
- `trigger_eval.py`: trigger cases cover GWAS figure creation, existing-figure edits, reference-guided comparison, near-neighbor script edits and QA-only requests.
- `export_skill_ir.py`: exports platform-neutral intent and boundary evidence.
- `verify.py`/`pytest`: 94 tests and 121 subtests pass.
- Live R/Python rendering, fonts, journal-specific output, provider-backed comparison and human blind review are not certified by this handoff.
- The router cannot change sample size, P/FDR thresholds, clumping, LD reference, lead SNP rules or causal-language level.
