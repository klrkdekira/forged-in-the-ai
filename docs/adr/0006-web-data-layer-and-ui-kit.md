# 0006: Web data layer and UI kit

- Status: accepted
- Date: 2026-07-10

## Context

Extends ADR-0002's frontend decision (React, TypeScript, Vite) with the
concrete library choices for routing, server state, forms, and UI, chosen by
the project owner.

## Decision

- **TanStack Router** (file-based routes via the Vite plugin) and
  **TanStack Query** for server state.
- **React Hook Form + Zod** (`@hookform/resolvers`) for forms: sheet entry,
  session zero, guided playbook assembly.
- **Tailwind CSS v4 + shadcn/ui** for styling and components. shadcn
  components are vendored into `web/src/components/ui`: self-contained, no
  runtime component dependency, themable for the game's look.

Integration rules:

- Generated types remain the contract (ADR-0002): `openapi-typescript`
  from the server's OpenAPI, with `openapi-fetch` as the typed client feeding
  Query. Zod schemas are for form-level validation UX only; server-side
  Pydantic validation stays authoritative. Never hand-mirror server models in
  Zod.
- WebSocket and the Query cache: the session WS channel (FR-30) is the write
  path for live state, and incoming deltas patch or invalidate Query caches.
  Queries fetch initial state; the socket keeps it current. No polling.
- Engine mutations (mark stress, tick clock; FR-28) are Query mutations
  hitting engine-operation endpoints, with optimistic updates only where the
  operation cannot be refused by the engine.

## Consequences

- Form-heavy flows (guided entry, session zero) get robust validation UX
  without duplicating the schema source.
- shadcn/ui's copy-in model adds vendored code to review but keeps the image
  self-contained and the design system modifiable; clocks and sheet widgets
  will be custom components built the same way.
- TanStack Router's typed routes pair with generated API types, so route
  params and loader data stay type-safe end to end.
