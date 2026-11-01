# Routing evidence and entry contracts

The router discovers candidates; the agent reads source instructions and chooses a route. A retrieval score is not confidence, a stored record is not a live model benchmark, and file checks are not scientific backend tests.

## Task and responsibility

Before searching, inherit the scientific question, input state (existing code, raw observations, accepted results, image, or design only), source language, explicit skill, output requirements and already confirmed style. Existing code is a valid execution target. Domain evidence is separate from chart words and style names.

Use backend filtering for the code to be preserved or generated. A palette, QA tool or editable-slide reconstruction helper need not use that same backend. `--intent palette`, `qa`, `reconstruct`, and `reference` scope the query to that responsibility. Read actual requirements before selecting any candidate.

For filtered queries, `candidates` have reviewed metadata meeting those filters. `review_candidates` need source reading before compatibility can be decided; their presence must not be described as execution readiness. Historical metadata is useful to locate a changed installation, but cannot certify its current capabilities. Unfiltered discoveries also require source reading.

## Concrete entry points

Curated `entry_points` are navigation hints, not a unified third-party function API:

| Field | Meaning |
|---|---|
| id / entry_path | Unit, template or function and its path relative to the skill |
| backend | Actual implementation language; outputs are separate |
| input_kind / required_inputs | Existing code, raw observations, accepted results, images, or design; minimal input requirements |
| analysis_effect | `none`, `refit_or_test`, or `unknown` |
| source_kind | Generic template, project adapter or reference |
| outputs / constraints | Deliverable formats and limits that matter to selection |
| source_sha256 | Reviewed concrete source snapshot, when available |

Read the selected entry at use time. An existing file may require missing packages, project-specific data or external tools. A changed hash means re-read it. A matching hash only means the reviewed text is unchanged.

For results-only tasks, do not execute `refit_or_test` or unknown analysis paths without resolving the conflict. Borrowing a layout is different from executing its original project analysis. Check P/FDR selection, thresholds and filtering against the declared task even when a template is described as generic.

## Optional route records

Most user-facing explanations need only one or two sentences. The following JSON is for development/review, not a form users must fill in and not arguments passed to third-party skills:

```json
{
  "case_id": "r-existing-edit",
  "execution_target": "existing_code",
  "primary_skill": null,
  "helpers": [],
  "language": "R",
  "read_files": ["examples/fixtures/existing_forest.R"],
  "entry_point": "examples/fixtures/existing_forest.R",
  "actions": ["inspect_existing_code", "plan_edit", "preserve_results", "preserve_language"],
  "verification_level": "route_dry_run",
  "notes": "Keep the existing script; change only requested labels or styling."
}
```

Skill routes set `execution_target` to `skill`, name a `primary_skill`, and record the selected SKILL and relevant entry files in `read_files`. `entry_point` can be null when no executable entry has been selected. Missing input must be reported; do not invent an existing file or claim a render.

`scripts/check_routes.py` validates record coverage and mechanical boundaries against `test-prompts.json`. It checks language, explicit skill, allowed direct-code routes, forbidden primary choices and forbidden actions. Unknown actions, missing/duplicate records and invalid structures fail. Natural-language scientific conditions require independent source/trace review. The validator cannot establish that a model really read a file or that its proposed visual design is correct.

## Three distinct verification layers

1. `python -B scripts/verify.py`: deterministic isolated discovery, regression, catalog/acceptance contracts and negative trace fixtures; no third-party skills or network required.
2. Independent route dry-runs: execute real searches, read selected installed sources, record decisions and inspect the trace. Report their commands and evidence separately from unit tests.
3. Actual figure tasks: run the selected backend on authorized inputs and inspect the delivered figure. This release's router checks do not certify that layer.

When changing retrieval, compare the same fixtures to the frozen previous revision. Preserve no-match and known-incompatibility cases alongside positive examples. Do not optimize a single top result while dropping current code, unit language, scientific inputs or requested output constraints.
