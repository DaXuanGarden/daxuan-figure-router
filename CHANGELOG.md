# Changelog

## Unreleased — GWAS figure contracts

- Add a versioned FigureBrief validator and six display-only GWAS figure recipes.
- Add synthetic LST–CVD recipe fixtures for correlation, PLACO+/coloc, locus and gene-level
  candidate planning without rerunning upstream statistics.
- Support an explicit `project_root` for project-relative input-path checks.

## Unreleased — portable Skill dependencies

- Add explicit offline plan/status and pinned-source installation profiles; discover real installed identities and skip them without updating or replacing.
- Preserve source licences and per-file receipts, stage complete bundles, and distinguish unavailable origins from missing runtime packages/services.
- Keep ordinary routing discovery read-only; freshly installed public variants require reading their actual contracts before use.

## Core routing reliability

- Keep source-changed and unregistered skills visible as bounded review candidates without claiming backend compatibility; use current reviewed metadata for capability filtering.
- Separate task intent, domain evidence and chart terms; normalize common Chinese terms and domain aliases, prefer Latin word matches, and expose vocabulary diagnostics.
- Return compact search/list summaries with match evidence; `show` and `--details` expose full metadata. Consumers needing the old full candidate objects should request details.
- Distinguish drawing backends from output containers and scope helper queries to their actual responsibilities.
- Add reviewed entry contracts for common templates, including accepted-results versus raw-data inputs, model-refitting behavior and historical project adapters.
- Allow direct edits of existing code without an extra primary skill; preserve explicit choices, source languages and accepted results.
- Add a single offline verification command, route-record validation, regression fixtures, independent route replay guidance and updated CI.

## v0.1.0 — 2026-11-01

Initial release of the local scientific figure skill router.

- Route create, edit, chart selection, palette, QA, and diagram requests while preserving explicit skill and language choices.
- Discover installed skills with read-only `list`, `search`, `show`, and `doctor` commands.
- Provide 39 curated capability cards, with exact path binding, content hashes, live resource checks, and duplicate-family hints.
- Discover unregistered skills without assuming their language or execution compatibility.
- Exclude copies of the router itself, including when running the CLI from a standalone checkout.
- Include 8 isolated CLI regression checks, 16 routing acceptance prompts, installation instructions, and CI.

The capability cards are a reference snapshot. Referenced third-party skills and assets are not bundled. Routing scores retrieve candidates; the agent must read the selected skill and apply task constraints before execution. Scientific figure backends are not certified as runnable by this release.
# Unreleased

- Added GWAS figure recipes for global genetic correlation, PLACO+/coloc shared loci,
  gene-level results and MR, including evidence-layer and annotation boundaries.
- Added a synthetic LST–CVD recipe dry-run with a FigureBrief and candidate-comparison
  documentation. The fixture contains no real study data and does not execute a renderer.
