# Multi-candidate figures and portable skill installation

The user requested implementation after planning: compare genuinely different forms and styles from one dataset, let authors select, and let colleagues install missing routed skills without reinstalling existing ones. The baseline is commit `b643e57`; its 26 tests pass. This remains one router Skill with optional tools. We use one bounded execution plan and phase gates; no persistent Codex Goal is created without an explicit request to start one.

## Product choices and failure review

- Preserve the existing quick single-figure/edit route. Enter comparison mode when requested or when the author wants alternatives. Start with 4–6 purposeful candidates, normally at most 12; do not enumerate every form × palette combination.
- Separate scientific form, layout/typography and palette. Chart eligibility follows the scientific question and experimental unit. A different colour alone is not a different chart form. Journal-inspired appearance is not official submission compliance.
- Reuse actual installed renderers and palette skills. The router owns candidate planning, collection, evidence and selection; it is not a new universal plotting or statistical backend.
- Freeze the data and scientific contract. Style rerendering must not silently rerun inference. In particular, some existing `recolor` implementations call the original analysis again; inspect code and compare actual analysis records.
- The smallest visible workflow is plan → real previews → local comparison gallery → author selection → retained decision record. Plans, mock images and missing-runtime reports must never be labelled rendered figures.
- Public installation needs verified origins, immutable refs and licences. A local custom skill without a public source cannot be made installable by guessing a similar name. Standard Skill installation does not execute arbitrary dependency hooks; provide an explicit bootstrap command and an authorized first-use workflow.

## Frozen shared contracts

### Comparison tool (`scripts/comparison.py`)

Standard-library commands: `plan --brief FILE --outdir DIR`, `assemble --plan FILE --results FILE`, `check --run DIR`, and `select --run DIR --id ID --reason TEXT` (optional choice-file import may be added). No arbitrary plotting commands are executed.

Brief JSON: `schema_version: 1`, `title`, `input_file`, `language` (`R`, `python`, `matlab`, `any`), `canvas_mm: [width,height]`, non-empty `data_contract` object, optional `analysis_file`, and 2–12 `variants`. Each variant has safe unique `id`, `title`, `form`, `style_family`, `rationale`, `primary_skill` (string or null for existing code), `helpers` (strings), and optional `target_context`, `style_parameters`, `entry_point`. Form/style labels must be distinct as pairs. Source paths in a brief resolve relative to that brief.

`plan` creates a fresh directory, copies the input to a snapshot, records its SHA-256, freezes the scientific contract and configuration, and seals the plan. Expose `data_sha256` and `science_sha256` for provider receipts. Preserve original inputs; refuse to overwrite an existing run.

Results JSON: object with `variants` array, exactly one row per planned ID. Each row has `id`, `status` (`rendered` or `blocked`). Blocked rows require `reason`. Rendered rows require `preview` (real PNG), `language`, `canvas_mm`, `data_sha256`, `science_sha256`, `analysis_file` (actual JSON record; identical canonical scientific analysis across candidates), and `qa` (`status`: `unreviewed`, `pass`, `fail`; optional notes/evidence). Optional `svg`, `pdf`, `code`, `provenance` are retained as evidence. Paths resolve relative to the results file. Missing outputs, changed inputs/contracts/analysis, wrong language, inconsistent canvases and duplicate image content must be exposed or rejected, never silently counted as success.

`assemble` creates real copied assets, a local responsive `gallery.html` and evidence `gallery.json`; metadata stays outside manuscript artwork. No remote scripts or image requests. Distinguish rendered draft/QA-failed/blocked. Incomplete collections remain visibly partial and return nonzero. `check` rechecks stored hashes/plan/input/assets without rendering. `select` accepts a rendered candidate that has not failed QA, stores an append-only decision history and latest selection; it never deletes alternatives or overwrites a production figure. Selection means selected for refinement, not publication-ready. HTML may export a choice request for the agent/CLI to validate and record.

### Dependency tool (`scripts/skill_bundle.py`)

Standard-library `plan`, `status`, `install`; common `--manifest`, `--profile`, repeatable `--skill`, `--target`, repeatable `--scan-root`. Default target is the configured Codex skills directory. Explicit scan roots isolate discovery for tests; default discovery also checks normal user/project/Agent roots. Read-only plan/status make no directories, downloads or installations.

`references/skill-sources.json`: `schema_version: 1`, `skills` array, `profiles` object. Each skill has `id`, `name`, `target_dir`, `status` (`verified_public`, `system`, `unavailable`), `reason`, optional `requires` (other source IDs), `runtime_requirements` (informational). Verified public entries require `repository` (`owner/repo`), `ref` (40-char immutable commit), `path` (safe repository-relative skill directory, `.` permitted), `skill_sha256`, and `license` with `spdx`, `path`, `url`; optional `include_repo_files` preserves root licence material outside a subdirectory. Profiles map names to objects with `description` and `skills` IDs. Keep all existing curated identities represented, including unavailable ones; new public identities are explicit additions, not aliases for custom skills.

`install` is the explicit mutation boundary. Resolve required skills, skip valid existing identities in any scanned root without updating/replacing them, report destination conflicts and unavailable sources, stage verified complete source files from the pinned public revision, verify SKILL identity/hash and fetched contents, then publish only new directories and save receipts. No package managers, setup scripts or downloaded code execute. No forced upgrades, deletions, guessed URLs, credentials in output, or modification of original skills. Interrupted/failed downloads must not leave a completed-looking skill. Runtime libraries, external services and API keys are distinct from installing Skill files and remain reported requirements.

## Invariants and proof surfaces

| Invariant | Evidence |
|---|---|
| Same accepted data and scientific meaning across visual alternatives | Frozen input/contract, actual analysis record comparison, negative tests and manual figure inspection |
| No invented candidate diversity | Form/style labels, duplicate-content detection, explicit rationale and contact sheet |
| A technical failure cannot become an aesthetic rejection | Separate blocked/failed/unreviewed states with reasons |
| Authors control the final direction | Real gallery and retained validated selection event |
| Existing single/edit routes remain available | Original 26 tests and route instructions |
| Existing skills are not overwritten or reinstalled | Isolated install/repeat/conflict tests and a real fresh-directory smoke test |
| Missing public sources remain visible | Source registry and plan diagnostics covering every curated identity |
| Completion is not a CI status assertion | Actual render/preview/selection, source receipts, hashes, browser checks and CI log inspection |

## Phases and ownership

1. Freeze baseline, inspect actual sources, research peers, challenge assumptions. No implementation until shared fields above stabilize.
2. Dependency surface: owner changes only `scripts/skill_bundle.py` and `tests/test_skill_bundle.py`; primary owns the source registry, documentation, CI and index integration. Gate: offline tests plus a genuine pinned install followed by a zero-download repeat.
3. Comparison surface: separate owner changes only `scripts/comparison.py` and `tests/test_comparison.py`; primary owns renderer examples, fixtures, SKILL, README and design references. Gate: offline negative tests plus genuine previews and a selection event.
4. Primary integrates both, keeps `scripts/verify.py` as the single offline gate, creates reproducible showcase/data/source, checks desktop/mobile gallery and source preservation. No third-party skill modification.
5. Fresh independent QA reviews the integrated features and real outputs. Primary runs final checks, syncs local installation, and updates the already-authorized GitHub repository in separately verified commits. Commit then push; read actual CI logs.

Research agents write artifacts only. Implementation agents report shared-contract gaps rather than silently modifying the contracts or each other's files. Maximum useful concurrency is four including the primary. This iteration does not add a literature platform, paid image generation, a web service, universal plotting backend, arbitrary remote installer, or automatic statistical analysis.
