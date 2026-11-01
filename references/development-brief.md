# Core routing reliability: execution brief

This iteration implements the five findings from the v0.1.0 audit: metadata freshness, task/domain/chart retrieval, concrete entry contracts, direct code edits, and reproducible routing verification. It remains one local Skill with a standard-library CLI. A normal task is sufficient; no persistent Codex Goal is created.

The user requested implementation of all reviewed core improvements and an update to the existing GitHub repository. Scientific backend certification, literature/inspiration platforms, automatic installations, modifying third-party skills, new services, and a new release tag are outside this iteration.

## Invariants and proof

| Invariant | Proof |
|---|---|
| Stale/unregistered metadata never proves compatibility | Disposable source-change/new/moved fixtures |
| Unknown candidates remain visible without claiming compatibility | Separate bounded `review_candidates` with explicit state |
| Exact path binding and same-name separation remain intact | Existing discovery tests |
| Query score is evidence, never probability or permission to execute | Field evidence and unchanged read-before-select boundary |
| Backend language and output format are distinct | Catalog fields, helper intent regression |
| Existing code can be the execution target with no primary skill | Acceptance contract and trace checker |
| Accepted results never authorize refitting upstream analysis | Entry `input_kind`/`analysis_effect`, forbidden actions, source review |
| Discovery is read-only and executes no backend | Filesystem snapshots and marker fixture |
| Verification works without installed third-party skills | Isolated fixtures plus explicit independent live route dry-runs |

## Shared contracts (freeze before delegation)

CLI keeps `list`, `search`, `show`, `doctor`; adds `vocabulary`. `search`/`list` return compact summaries by default, `--details` expands them, and `show` remains detailed. `candidates` contains matches passing verified filters (or unfiltered discoveries); filtered unknown/stale matches go in a separate `review_candidates`, bounded by `--review-limit` (default 3). Review entries must be marked as needing source reading, never compatible. Known mismatches do not enter that fallback. Source changes keep historical catalog information only for inspection/identity, not positive capability filtering or ranking.

Filters add optional `--intent`: create, edit, choose, palette, qa, diagram, reconstruct, reference, maintenance. `--language` constrains the source-code drawing responsibility; palette/qa/reconstruct/reference queries do not inherit a source drawing backend restriction. Explain that scope in output. Normalize explicit aliases (`generic`→`general`, `clinical`→`medical`); unknown domain/tag values return a useful diagnostic with available values. Query extraction handles common Chinese chart phrases; Latin whole-word evidence is stronger than substring fallback. Specialized domain candidates without domain evidence must not outrank a matching general drawing capability solely through generic chart words.

Catalog keeps exact path/source hashes. Add optional `intents`, `backends`, `outputs`, `entry_points`; legacy `languages` contains backends only, never SVG/PPTX containers. Entry points use `id`, `entry_path`, `backend`, `input_kind`, `required_inputs`, `analysis_effect` (`none`, `refit_or_test`, `unknown`), `source_kind`, `outputs`, `constraints`, and reviewed `source_sha256` when a concrete file is inspected. Entry existence/hash is navigation evidence, never a runtime guarantee. Unknown or mixed analysis behavior cannot be treated as a results-only renderer. Do not copy third-party code.

Acceptance prompts keep their current structure. Edit cases may add `expected.allow_existing_code: true`; a record using existing code sets `execution_target: existing_code` and `primary_skill: null`. Skill routes use `execution_target: skill` and a primary from `primary_any_of`. Trace records contain `case_id`, `execution_target`, `primary_skill`, `helpers` (skill-name strings), `language`, `read_files`, `entry_point`, `actions`, `verification_level: route_dry_run`, and optional notes/evidence. Hard language, explicit skill, forbidden primary and forbidden upstream actions are checked mechanically; free-text scientific conditions still require independent review. Trace validation does not prove a live model will reproduce the route or that a figure was rendered.

## Phase gates and ownership

1. Baseline/preflight: clean v0.1.0 and audit evidence inspected; freeze baseline outside the source checkout.
2. Contracts: this file fixes fields and responsibility boundaries before parallel edits.
3. Core: retrieval owner changes only index CLI and its tests; catalog owner changes only catalog/acceptance prompts; verification owner changes only trace checker, verifier, and their tests. Report contract gaps before changing shared fields.
4. Integration: primary agent owns SKILL, README, examples, CI, changelog, integration fixes and live CLI checks.
5. Independent QA: review final files; replay actual installed-skill route cases; distinguish failures from unavailable inputs and dry-runs from rendered figures.
6. Completion: primary runs fresh `python -B scripts/verify.py`, exercises actual CLI workflows, synchronizes the existing local installation preserving unrelated files, pushes the authorized repository update, and checks actual CI logs for the pushed commit.

Maximum useful implementation concurrency is four agents including the primary. Sub-agent reports are review inputs; final completion depends on files, fresh commands, live workflow output, remote commit and CI evidence.
