# Architecture

## Routing

Uses Next.js App Router. All routes live in `src/app/`. Routes should be
thin — they import page components from the relevant module's `pages/`
folder and render them.

Example:

```tsx
// src/app/graph/page.tsx
import { GraphPage } from '@/modules/graph/pages/GraphPage';
export default GraphPage;
```

## Module structure

All business logic lives in `src/modules/`. Each module is a
self-contained domain slice:

```
src/modules/
├── common/             # Shared across ALL modules — the only permitted cross-module import
│   ├── api/            # Shared fetch helpers, API client setup
│   ├── components/     # Design-system-level shared components
│   ├── context/        # App-wide React contexts
│   ├── hooks/          # Shared hooks (e.g. useDebounce, useLocalStorage)
│   ├── models/         # Shared TypeScript types/interfaces
│   └── utils/          # Shared pure utilities
└── <feature>/          # One directory per domain (graph, runs, review-queue, …)
    ├── api/            # Fetch functions / hooks for this module's backend endpoints
    ├── components/     # UI components used only within this module
    ├── context/        # Module-scoped React context
    ├── hooks/          # Custom hooks specific to this module
    ├── models/         # TypeScript types/interfaces for this module
    ├── pages/          # Top-level page components; imported by src/app/ routes
    └── utils/          # Pure utilities specific to this module
```

### Module boundary rule

**Modules may only import from `common` or from within themselves.**

```
✅ src/modules/runs/components/RunsList.tsx
     → imports from @/modules/runs/hooks/useRuns        (same module — OK)
     → imports from @/modules/common/components/Badge   (common — OK)

❌ src/modules/runs/components/RunsList.tsx
     → imports from @/modules/graph/hooks/useGraph       (cross-module — LINT ERROR)
```

Enforced automatically by the `no-restricted-imports` ESLint rule. If two
modules need the same piece of code, move it to `common`.

## State management

- Local state: `useState` / `useReducer`
- Module-scoped shared state: React Context in `<module>/context/`
- App-wide shared state: React Context in `common/context/`
- Server state / data fetching: to be decided when the API client layer
  is built (Plan B step 1) — see
  [`../../docs/13-spec-backend-api.md`](../../docs/13-spec-backend-api.md)

## Data fetching

This UI's only backend is the local FastAPI service described in
[`../../docs/13-spec-backend-api.md`](../../docs/13-spec-backend-api.md).
No Server Components fetching from external/cloud services — this is a
local-only SPA behind a local backend (see root `CLAUDE.md`, "Workflow
visualization & execution UI: local only, no cloud accounts").

## Styling strategy

- **shadcn/ui** — component source copied into `src/components/ui/` via
  `npx shadcn@latest add <component>`, not an npm dependency. Built on
  Tailwind CSS + Radix/Base UI primitives.
- **Tailwind CSS** — utility classes for layout, spacing, and styling
  both shadcn components and custom components.

## Environment variables

Store in `.env.local` (gitignored). Prefix public vars with
`NEXT_PUBLIC_` (e.g. the local backend base URL).
