# Frontend Testing Strategy

This repo has a dedicated frontend app in `apps/web-ts` built with Vite, React, TypeScript, Tailwind, and shadcn/ui. The current test stack is Vitest with `jsdom` and `@testing-library/react`, wired through `apps/web-ts/vitest.config.ts`.

## Current State

There is already a small but useful baseline of frontend tests:
- `apps/web-ts/src/pages/HROps.test.ts` covers queue mapping, filters, and sorting helpers.
- `apps/web-ts/src/components/MyRequestsPanel.test.tsx` covers tab filtering and request-expansion behavior.
- `apps/web-ts/src/test/setup.ts` sets up `jest-dom` and browser shims for Vitest.

The biggest gaps are the user-facing flows that combine state, API calls, and routing:
- chat send/receive flows in `Chat.tsx` and `HRChat.tsx`
- auth-gated rendering and redirect behavior
- session list/create/delete behavior
- HR request and escalation actions
- loading, empty, and error states for backend-driven screens

## Recommended Test Pyramid

1. Keep most coverage in component and hook tests using Vitest + Testing Library.
2. Add page-level integration tests for the highest-value flows with mocked API responses.
3. Add a very small number of end-to-end tests for the critical journeys only.

Recommended stack for the missing layers:
- `Vitest` for unit and component tests
- `@testing-library/react` for behavior-driven assertions
- `MSW` for stable API mocking in page/integration tests
- `Playwright` for a few smoke tests if browser-level coverage is needed later

## Priority Flows To Cover

- Chat flow: send a message, receive a response, persist session state, and handle error/retry states.
- HR queue flow: list requests, filter/sort them, open a request, and apply status transitions.
- My requests flow: switch tabs, expand a request, and verify view counters or badges.
- Auth flow: unauthenticated redirect, role-based visibility, and protected-route behavior.
- Ticket actions: accept, update, resolve, and add notes from the HR side.

## Suggested Conventions

- Put component tests next to the component when the behavior is local and obvious.
- Put page-level tests in `src/pages/*.test.tsx` when the flow crosses multiple components or contexts.
- Prefer user-visible assertions over implementation details.
- Mock network and storage boundaries; avoid real Supabase or backend calls in Vitest.
- Keep test fixtures in small local helpers so request/session payloads stay readable.
- Cover loading, empty, and failure states alongside the happy path.

## Short-Term Gaps

- `Chat.tsx` and `HRChat.tsx` have the most value and the least direct test coverage.
- Context providers such as `AuthContext` and `HRTicketsContext` need flow tests around role changes and assigned-ticket behavior.
- There is no browser E2E suite yet, so any true end-to-end coverage is still a future addition.

## Suggested Next Step

Start with page-level tests for chat and queue flows, then add a small `MSW` layer for API mocking. After that, add Playwright only for the paths that must be verified in a real browser.
