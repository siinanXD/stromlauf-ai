# Copilot coding agent — Stromlauf AI

Read `AGENTS.md`, `README.md`, `frontend/AGENTS.md` and the assigned issue before changing anything.
The product contract and plan are in `docs/product/` (contract, architecture, ux-spec, cost-model).

Rules:
- One issue per pull request; title prefixed with the issue key (e.g. `MB-2:`); fill the acceptance checklist in the PR.
- Run `python scripts/check.py` (ruff, pytest, eslint, tsc, vitest) before pushing; CI runs the same on every PR.
- Deterministic first: exact facts from the tag index, parsers and SQL; models only for unstructured content. No new agents, no new frameworks without a reason stated in the PR.
- Every AI call must be traced and its cost recorded (see `docs/product/cost-model.md`); no per-question image generation.
- Never commit secrets; `.env.example` carries names only. Customer documents never go into fixtures.
- German UI copy (du-Form), technical, no placeholders.
