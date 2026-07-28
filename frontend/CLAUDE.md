@AGENTS.md

# frontend — Claude context

Scoped to this directory. Project-wide non-negotiable rules (Plan Mode,
no fabrication, tests required, only official libraries, etc.) live in
the root [`CLAUDE.md`](../CLAUDE.md) and still apply here.

## Project type

Next.js 16 (App Router), TypeScript strict mode, React 19.

## Build & dev commands

- Dev server: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`
- Format: `npm run format`
- Tests: `npm test`

## Key conventions

- TypeScript strict mode — no `any`, no implicit returns
- Named exports only (except Next.js required defaults: `page.tsx`, `layout.tsx`)
- Import order enforced by ESLint (builtin → external → internal)
- **shadcn/ui** for components (not Mantine — see root `CLAUDE.md`,
  "Confirmed tech stack decisions"). Components are copied into
  `src/components/ui/` via `npx shadcn@latest add <component>`, not
  installed as an npm dependency.
- Tailwind CSS for layout/spacing utilities and for styling shadcn
  components (shadcn components are themselves Tailwind-based)
- All components must have a co-located `.test.tsx` file
- Commit format: `feat|fix|chore|refactor(scope): description`

## Module architecture

Code is organised into feature modules under `src/modules/`:

- `common/` — the only module that can be imported by other modules.
  Shared components, hooks, API helpers, types, utils, contexts.
- `<feature>/` (e.g. `graph`, `runs`, `review-queue`) — self-contained
  domain modules. Each has: `api/`, `components/`, `context/`, `hooks/`,
  `models/`, `pages/`, `utils/`.

**Module boundary rule (enforced by ESLint):** modules must NOT import
from each other. A module may only import from:

1. Its own files
2. `@/modules/common/**`
3. External packages

If code needs to be shared between two feature modules, move it to
`common`.

## Folder conventions

- `src/app/` — Next.js routes and layouts only; no business logic here
- `src/modules/common/` — all cross-module shared code
- `src/modules/<feature>/pages/` — top-level page components, imported by
  `src/app/` routes
- `src/components/ui/` — shadcn/ui generated components (not hand-edited
  beyond what `shadcn add` produces)
- `src/test/` — Vitest setup

## Testing

- Vitest + Testing Library
- Run: `npm test`
- Coverage: `npm run test:coverage`

## Data source

This UI's only backend is the local FastAPI service described in
[`../docs/13-spec-backend-api.md`](../docs/13-spec-backend-api.md). No
other network calls, no cloud accounts (see root `CLAUDE.md`, "Workflow
visualization & execution UI: local only, no cloud accounts").
