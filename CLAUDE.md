<!-- Everything from here up to "Project rules": verbatim from multica-ai/andrej-karpathy-skills CLAUDE.md (commit 2c60614), MIT License. -->

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Project rules (ha-fluidra-pool)

- **KISS**: one simple, correct `fluidra_pool` integration. Minimum code, no speculative
  options or abstractions, delete > add. Touch only the files the task names.
- **Compatibility invariants** (existing users must not lose entities): domain `fluidra_pool`;
  config entry `unique_id = f"fluidra_pool_{username}"` with `username`/`password` data still
  readable (add a migration if the schema changes); device identifiers `(DOMAIN, device_id)`;
  entity unique IDs `fluidra_{device_id}_climate_heatpump`,
  `fluidra_{device_id}_water_temperature`, `fluidra_{device_id}_error_information` kept.
  Removed entities go in `CHANGELOG.md` as breaking changes.
- **Secrets**: never log, print, commit or echo passwords, access/refresh tokens or email
  addresses (code, tests, fixtures, diagnostics, commit messages included).
- **One task = one commit** on branch `finalize-v1`, message `T<NN>: <title>`; do not push.
- **How to run tests**: See T04 — to be filled.
- Full decisions, facts and invariants: `backlog/README.md` (it wins if this summary drifts).
