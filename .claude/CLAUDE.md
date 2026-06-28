# CLAUDE.md

## Attribution

This document was developed for this project and incorporates ideas and adapted text from:

- https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md (MIT License)
- https://github.com/affaan-m/ECC/blob/main/rules/common/coding-style.md (MIT License)

Content has been modified and extended for this repository.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

Before writing any code, explain in plain English:
- What files you will create or modify.
- What each function expects as input and returns as output.
- Any packages you intend to add.

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

## 5. Engineering Guidelines

- Prefer small, reviewable changes over large refactors.
- Ask questions instead of inventing missing information.
- Do not use 42 as a random seed. [Relevant substack here](https://fetchdecodeexecute.substack.com/p/stop-using-42-as-a-random-seed)

## 6. Project principles

1. Educational first.
2. Maps are the primary interface.
3. Data should remain separate from presentation.
4. Every expedition should be mostly self-contained.
5. Shared assets should only contain code used by multiple expeditions.
6. A new expedition should require creating one new folder rather than editing many files.
7. Prefer static files over generated infrastructure.

## 7. Architecture

- When uncertain where code belongs, ask before implementing.

## 8. Claude Code GitHub workflow

Claude Code may assist with implementation.

Claude Code should not:

- push directly to the main branch
- decide project scope
- add unrelated features

## 9. Core Principles

### KISS (Keep It Simple)

- Prefer the simplest solution that actually works
- Avoid premature optimization
- Optimize for clarity over cleverness

### DRY (Don't Repeat Yourself)

- Extract repeated logic into shared functions or utilities
- Avoid copy-paste implementation drift
- Introduce abstractions when repetition is real, not speculative

### YAGNI (You Aren't Gonna Need It)

- Do not build features or abstractions before they are needed
- Avoid speculative generality
- Start simple, then refactor when the pressure is real

## 10. When Stuck

- If the correct location for new code is unclear, ask.
- If documentation is missing or contradicts the code, flag it — don't resolve it silently.