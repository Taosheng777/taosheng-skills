---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
license: MIT
---

# Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Use judgment:** Preserve the user’s goal and scope; match investigation and verification to the consequences of being wrong.

## 1. Think Before Coding

**Make material assumptions visible and resolve uncertainty with evidence.**

Before implementing:
- Inspect the request, current code, and project conventions before asking the user.
- Choose a reasonable default for reversible implementation details; state assumptions when they affect the result.
- If a simpler approach exists, use it or explain the meaningful tradeoff.
- Ask only when information cannot be obtained and materially changes the goal, acceptance criteria, authorization, or irreversible consequences. Continue independent work while that answer is pending.
- Carry existing authorization through the same task; do not seek permission again for already authorized edits, validation, or necessary retries.

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

Choose verification that proves the requested behavior. Tests are useful for core logic, recurring bugs, and maintained code; small reversible edits may only need an appropriate direct check. Examples:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Continue until the requested result is implemented and the relevant checks pass. If a real blocker remains, identify the blocked step and complete unaffected work; do not substitute a plan or partial fix for completion.
