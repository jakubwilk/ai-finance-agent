# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Non-negotiable rules

These override default behavior and apply to every task in this repo, no exceptions.

1. **Never fabricate anything.** If you don't know something, aren't sure, or a piece of information needed to proceed is missing — ask the user. Do not assume; the real answer is often not what you'd guess.
2. **Check documentation before guessing, and before asking.** When unsure how to implement something technically, consult the relevant technology's docs first (see [Documentation references](#documentation-references-llmstxt) below) rather than guessing from memory. Only ask the user once you've checked and are still unsure — be confident in what you propose, don't wing it.
3. **Every change goes through Plan Mode first.** Any create, modify, or delete operation — code, files, config — must be planned via Plan Mode (`EnterPlanMode`) and presented to the user for review. Wait for explicit approval before executing. No direct edits outside this flow.
4. **Every feature needs tests.** Nothing is considered done without tests that prove the use case was actually analyzed and verified — not just "it runs."
5. **Use 2026 best practices, not outdated patterns.** Apply current best practices for the language/framework in use. When a canonical practices reference exists for a technology, add its link to the Documentation references section below so it's reusable.
6. **Never handle secrets in plaintext / in context.** Never ask the user to paste API keys, passwords, tokens, or other sensitive values into the conversation. Secrets live in `.env` files (Python/React side, if present in the environment) or `.claude/settings.local.json` — reference them by name, never inline their values in chat, code, comments, or commits.
7. **Only official, established libraries.** Don't introduce a custom/unofficial/unmaintained library for a given technology without asking first. If a task seems to require one, stop and flag it to the user, explain why, and wait for explicit approval before installing anything.
8. **Split complex work across dedicated subagents.** For a complex/multi-part operation, don't handle everything in one pass — break it into discrete tasks and delegate each to its own subagent (via the Agent tool), scoped to a single responsibility. Prefer several focused, single-purpose agents over one agent juggling multiple unrelated jobs.

## Project status

**AI Finance Agent** — this repository is currently empty. No source files, dependency manifests, or configuration exist yet.

There is no established build, lint, test, or run process, and no architecture to describe, because no code has been written.

## Confirmed tech stack decisions

- **Backend / agent logic: Python.** Assume Python for all agent, tooling, and data-processing code unless told otherwise.
- **UI: React.** If/when a user-facing interface is built for this agent, it will be React-based (not another frontend framework).
- **Agent orchestration: LangGraph** (not plain LangChain, not Deep Agents). Decided in `docs/00-spec-overview-architecture.md` ("Wybór frameworka: LangGraph"): the process is a deterministic, branching pipeline with human-in-the-loop interrupts and persistent state across weekly runs — this fits `StateGraph`, not a single-tool-loop LangChain agent or Deep Agents' dynamic ad-hoc planning (steps here are known upfront). LangChain still shows up as a supporting library (e.g. structured output via `langchain-middleware`), just not as the orchestrator.

These are settled decisions — don't re-ask about language, UI framework, or agent orchestration framework. Everything else about the stack (data sources, deployment specifics) is still open.

## Workflow visualization & execution UI: local only, no cloud accounts

**Decision:** the React UI must let the user see the graph/node structure of LangGraph workflows, trigger runs, and inspect execution history — all fully local, with no sign-up or external account required.

**Do NOT use LangGraph Studio or LangSmith for this.** Studio requires logging in with a LangSmith account even for local development (this was verified — it's not just an opt-in for tracing, it's required at login), so it violates the "no accounts" requirement. Don't reach for it by default just because it's the official tool.

**Approach to build instead**, using only LangGraph's native local APIs behind a small local backend:

- **Graph structure**: `graph.get_graph().draw_mermaid()` or `.draw_png()` — generates the node/edge structure locally, no network calls. Render it in the React UI (e.g., Mermaid.js or React Flow).
- **Execution history**: a local checkpointer (`SqliteSaver`, or local Postgres) persists state after every step. `graph.get_state_history(config)` returns full run history per `thread_id` — no external service involved.
- **Triggering runs**: a small local backend (FastAPI is the natural fit alongside the rest of the Python stack) exposes endpoints to `invoke`/`stream` the graph, list threads, and fetch state/history. The React UI calls this local backend only.

If a ready-made, fully self-hostable alternative is ever considered instead of building this by hand (e.g., Langfuse via Docker Compose), it still needs to run with zero external accounts — verify that before proposing it, don't assume from the tool's marketing.

## Personal financial data: never commit real values (repo is public)

**This repo is public on GitHub** (`github.com/jakubwilk/ai-finance-agent`).
This is a different concern from rule 6 (secrets/credentials) — this is about
the user's actual personal/financial reference data.

- Real content for `CATEGORIES` and `FIXED_COSTS` (category names, rent
  amounts, subscription costs, due dates, etc.) lives **only** in
  `data/local/categories.json` and `data/local/fixed_costs.json`, both
  covered by `.gitignore` — never commit these files with real values.
- Only `data/local/*.example.json` (fake/placeholder values) are tracked in
  git, to document the JSON shape. See
  `docs/01-spec-data-model.md` for the exact field mapping (mirrors the
  `CATEGORIES`/`FIXED_COSTS` DB columns).
- When the backend is implemented, a seed script reads these local JSON
  files into Postgres — that script doesn't exist yet, since no backend code
  exists yet.
- If a similar situation comes up again (any new file holding real personal
  data instead of code/config), apply the same pattern: gitignored real file
  + committed `*.example` template, rather than inventing something new.

## Before doing anything else

When code is eventually added to this repo (or if you're asked to scaffold it), ask the user for:

- What "finance agent" should do (data sources, APIs, tools it needs access to)
- Whether a React UI is needed yet, or backend-only for now

Once real project structure exists, replace this file with accurate commands and architecture notes derived from the actual codebase — do not carry forward any assumptions from this placeholder.

## Available skills and when to use them

Invoke these via the Skill tool instead of doing the equivalent work by hand.

**Agent framework (Python) — LangGraph is the chosen orchestrator** (see "Confirmed tech stack decisions" above); LangChain is used only as a supporting library, not as an alternative orchestrator. Deep Agents skills are kept for reference but are not the chosen path for this project:

- **ecosystem-primer** — background reading on the LangChain/LangGraph/Deep Agents ecosystem; the orchestration framework choice itself is already settled (LangGraph), so don't re-run this to re-decide it.
- **langchain-dependencies** — package versions, install, and environment setup for LangChain/LangGraph/LangSmith/Deep Agents (Python).
- **langgraph-python-quickstart** — scaffold a minimal local LangGraph agent.
- **langchain-fundamentals** — `create_agent`, tools, middleware basics (used here for supporting pieces, not the top-level orchestrator).
- **langchain-middleware** — human-in-the-loop approval, custom middleware, structured output (Pydantic) — e.g. used for the LLM classification step in categorization.
- **langchain-rag** — retrieval-augmented generation: document loaders, splitters, embeddings, vector stores. Relevant if the agent needs to reason over financial documents/filings.
- **langgraph-fundamentals** — StateGraph, state schemas, nodes/edges, streaming. Load before writing any LangGraph code.
- **langgraph-human-in-the-loop** — `interrupt()`/`Command(resume=...)` approval patterns, e.g. before executing a trade or financial action.
- **langgraph-persistence** — checkpointers, thread_id, state/time-travel.
- **langgraph-cli** — `langgraph new/dev/build/deploy` and `langgraph.json`.
- **deep-agents-core** / **deep-agents-memory** / **deep-agents-orchestration** / **deepagents-python-quickstart** / **managed-deep-agents** — not used in this project (LangGraph was chosen instead); kept here only in case that decision is ever revisited.

**UI and general tooling:**

- **init-frontend** — scaffolds the React (Next.js) frontend when the UI is built: TypeScript, Tailwind, Mantine, Vitest.
- **claude-api** — reference for the Claude/Anthropic API (models, pricing, tool use, streaming, caching). Load this BEFORE writing any LLM integration code, agent loop, or tool-calling logic that calls Claude specifically.
- **dataviz** — design guidance for charts/graphs/dashboards. Load before building any financial chart, KPI tile, or visualization in the React UI.
- **run** — launches the app to verify a change actually works. Use before reporting a run/build/UI change as done.
- **security-review** — audits pending changes for security issues. Use before merging code that touches secrets, credentials, external APIs, or financial data handling.
- **simplify** — reviews changed code for reuse/simplification/efficiency after a feature is implemented. Quality only, not a bug hunt.
- **review** / **code-review** — reviews a GitHub PR or the local working diff, respectively.
- **update-config** — use for any change to `.claude/settings.json` (permissions, hooks, env vars), not for ordinary app config.
- **loop** / **schedule** — set up recurring or cron-scheduled agent runs (e.g., periodic market data checks). Use only when the user explicitly wants a recurring/automated task, not for one-off requests.
- **eval-engineering** — build/run Harbor evals for the agent (regression cases, verifiers) once there's an agent to evaluate.

Check the live skill listing in context for the full set and exact trigger conditions before assuming one of the above still applies as described.

## Documentation references (llms.txt)

Before guessing at LangChain or Vite APIs/behavior, fetch these instead of relying on training-data recall — they're maintained indexes of current docs:

- **LangChain / LangGraph / LangSmith**: https://docs.langchain.com/llms.txt
- **Vite** (the build tool/dev server — framework-agnostic, not React-specific): https://vite.dev/llms.txt (index) / https://vite.dev/llms-full.txt (full docs)
- **React** (the UI library itself): https://react.dev/llms.txt

There is no official `llms.txt` for Python itself (the language) — only for individual libraries/frameworks. If a new framework enters the stack, check whether it publishes an `llms.txt` before assuming its API from memory.
