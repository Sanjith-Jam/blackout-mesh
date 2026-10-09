# Issue #16 delivery — frontend regression coverage

**Status:** partial; issue remains open.

The former WIP branch duplicated a dashboard WebSocket that is now owned by the
shared store. Its stale dashboard change was intentionally excluded. The remaining
fixture, component-test, and power-edge coverage was adapted to the current pages.

## Delivered

- Vitest/Testing Library tests cover classroom loading/recovery, multi-scan,
  capacity debounce, rejected commands, protected essentials, polling cleanup,
  hospital sensor abstention, and edge-state rendering.
- `jest-axe` checks the classroom and hospital visualizer trees.
- Deterministic frontend fixtures are generated from the API; a backend test checks
  that their shapes stay aligned with live responses.
- A Playwright Chromium test navigates between the separate classroom and hospital
  routes and verifies each visualizer remains distinct.
- CI runs generated API drift, audit, fixture, component, and browser checks.

## Verification

- Backend suite: **158 passed**.
- Frontend production build: passed on Vite 8.3.4; existing large-bundle warning.
- API contract tests: passed.
- Vitest: **15 passed**.
- History DOM tests: **4 passed**.
- Playwright route test: **1 passed**.
- `npm audit`: **0 vulnerabilities** after upgrading the development toolchain.

## Remaining acceptance gaps

This is not the requested seeded, backend-backed journey across shortage, hospital
fault, backend restart/resynchronization, restoration, and history replay. The
Playwright test uses generated API fixtures. Keyboard-only interaction, reduced
motion, and supported-width overflow also need browser-level checks. Hardware was
not exercised. Do not close #16 until those checks are delivered and CI passes.
