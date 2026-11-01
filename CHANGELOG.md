# Changelog

## v0.1.0 — 2026-11-01

Initial release of the local scientific figure skill router.

- Route create, edit, chart selection, palette, QA, and diagram requests while preserving explicit skill and language choices.
- Discover installed skills with read-only `list`, `search`, `show`, and `doctor` commands.
- Provide 39 curated capability cards, with exact path binding, content hashes, live resource checks, and duplicate-family hints.
- Discover unregistered skills without assuming their language or execution compatibility.
- Exclude copies of the router itself, including when running the CLI from a standalone checkout.
- Include 8 isolated CLI regression checks, 16 routing acceptance prompts, installation instructions, and CI.

The capability cards are a reference snapshot. Referenced third-party skills and assets are not bundled. Routing scores retrieve candidates; the agent must read the selected skill and apply task constraints before execution. Scientific figure backends are not certified as runnable by this release.
