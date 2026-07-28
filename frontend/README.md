# frontend

React UI for the AI Finance Agent: local, private view into the
LangGraph workflow — graph structure, run history, categorization review
queue, manual trigger. See
[`../docs/14-spec-frontend-ui.md`](../docs/14-spec-frontend-ui.md) for
the full spec and [`../PLAN.md`](../PLAN.md) ("Plan B") for the
step-by-step build order.

## Tech stack

| Tool                                 | Purpose                |
| ------------------------------------ | ---------------------- |
| Next.js 16 (App Router)              | Framework              |
| TypeScript                           | Type safety            |
| shadcn/ui (Tailwind + Radix/Base UI) | Component library      |
| ESLint + import plugin               | Linting & import order |
| Prettier                             | Code formatting        |
| Husky + lint-staged                  | Pre-commit checks      |
| Vitest + Testing Library             | Unit / component tests |

## Getting started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

The backend (FastAPI, Plan A step 13) doesn't exist yet, so the UI talks
to an in-memory mock API client by default —
[`src/modules/common/api/`](./src/modules/common/api/). No `.env` file
is required; both variables fall back to sensible defaults in code.

| Variable                      | Default                                | Purpose                                                          |
| ----------------------------- | -------------------------------------- | ---------------------------------------------------------------- |
| `NEXT_PUBLIC_USE_MOCK_API`    | `true` (anything other than `"false"`) | Use the fixture-backed mock client instead of real `fetch` calls |
| `NEXT_PUBLIC_BACKEND_API_URL` | `http://localhost:8000`                | Base URL for the real backend, once it exists                    |

Set `NEXT_PUBLIC_USE_MOCK_API=false` in `.env.local` once the backend is
reachable — no code change needed.

## Available scripts

| Script                  | Description             |
| ----------------------- | ----------------------- |
| `npm run dev`           | Start dev server        |
| `npm run build`         | Production build        |
| `npm run lint`          | Lint + auto-fix         |
| `npm run format`        | Format all files        |
| `npm test`              | Run tests (watch)       |
| `npm run test:coverage` | Run tests with coverage |

## Project structure

```
src/
├── app/              # Next.js App Router routes and layouts only
├── components/
│   └── ui/           # shadcn/ui generated components
└── modules/
    ├── common/       # Shared cross-module code (components, hooks, utils, etc.)
    └── <feature>/     # Domain modules: graph, runs, review-queue, etc.
        ├── api/
        ├── components/
        ├── context/
        ├── hooks/
        ├── models/
        ├── pages/
        └── utils/
```

## Conventions

- Named exports only (no default exports except page/layout files required by Next.js)
- Imports ordered: builtin → external → internal (enforced by ESLint)
- Modules may only import from `common` or within themselves — cross-module imports are a lint error
- Components co-located with their tests (`Component.test.tsx` next to `Component.tsx`)

See [`CLAUDE.md`](./CLAUDE.md) for the full set of conventions this
directory follows.
