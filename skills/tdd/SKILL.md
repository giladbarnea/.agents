---
name: tdd
description: Testing standards and test-driven development. Load before writing any tests, including integration tests, regression tests, and test-first feature or bug work. Use for TDD and red-green-refactor.
last_updated: 2026-10-21
origin:
  url: https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd
  commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
  last_checked: 2026-10-21
  sync: manual
  adaptation: Includes local testing rules, standalone interface-design notes, and refactoring after green.
---

# TDD

Use these standards whenever writing tests. Use the TDD loop below for test-first work.
Read the project instructions, its `GLOSSARY.md` when present, and relevant architectural decisions before choosing test names and interfaces.

## Prove behavior through public interfaces

Tests must verify behavior that users or callers need, not implementation details.
Prefer integration-style tests through real public interfaces. Tests should survive internal refactors without changes.
Do not test private methods, mock internal collaborators, assert internal call order, or verify through side channels such as direct database queries.

Base test behavior and expected results on the spec, plan, or an independent worked example.
Do not derive expectations from the implementation or recompute the same algorithm inside the test.
A test that passes by construction cannot detect a defect.

Mock only at system boundaries, such as external APIs, time, or randomness.
Prefer a test database over a database mock. Do not mock away the behavior under test.
Read [test examples](tests.md) and [mocking guidance](mocking.md) for concrete patterns.

## Agree on what the tests must prove

Use the public boundaries and behaviors already agreed in the request, spec, or plan.
Before testing at another boundary, confirm it with the user. State what each proposed boundary catches and what it misses.
Focus on critical paths and complex logic instead of trying to test every possible case.
Fewer meaningful tests are better than many tests that cannot expose defects.

When the interface needs design work, consult [interface design](interface-design.md) and [deep modules](deep-modules.md).

## Make failure deliberate and informative

Define a falsification criterion before writing each test: which bad state must this test detect?
Make sure a failing test exposes that state, not a broken fixture, missing import, or exception in the test itself.
Read the failure before changing implementation code. A red caused by the wrong problem proves nothing.

Use assertion messages that show the expected and actual values.
Tests must not fail accidentally while inspecting a result. Keep expected application errors separate from test defects.
When mocking an external boundary, patch its real symbol rather than relying on a brittle hard-coded symbol path.
See [assertion and fixture examples](tests.md#make-test-failures-explain-the-behavior).

## Develop test-first in vertical slices

Do not write all tests first and then all implementation.
Bulk tests assume behavior before you understand the code and commit you to an unverified test structure.

For TDD, work through one behavior at a time:

1. **Red:** Write one test at an agreed public boundary. Run it and verify that it fails for the intended reason.
2. **Green:** Write only enough implementation to pass that test. Run the test again.
3. **Refactor:** Only after the tests pass, improve the code within the current scope. Keep behavior unchanged and rerun the tests.
4. Repeat with the next behavior, using what the previous cycle taught you.

The first cycle is a tracer bullet that proves one complete path through the system.
Do not add speculative features or implement behavior for a future test.
Never refactor while tests fail. Use the [refactor candidates](refactoring.md) after green.

This local skill keeps refactoring after green. Current upstream TDD assigns refactoring to a separate review skill.

## Check each cycle

- The test describes behavior through a public interface and survives internal refactors.
- Its expected result has an independent source of truth.
- Its failure exposes the intended bad state and explains what differed.
- The implementation is minimal and contains no speculative behavior.
- The relevant tests pass after implementation and after refactoring.
