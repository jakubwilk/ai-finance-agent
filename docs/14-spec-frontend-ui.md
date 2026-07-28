# 14 — Frontend UI

## Cel

Dać użytkownikowi lokalny, w pełni prywatny wgląd w strukturę grafu
LangGraph, historię uruchomień oraz możliwość ręcznego triggerowania runów
i przeglądu transakcji oczekujących na decyzję (`needs_review`) — bez
żadnego logowania do zewnętrznego konta.

## Zakres

Wchodzi: widok grafu, historia wykonań, panel przeglądu kategoryzacji,
ręczny trigger. Nie wchodzi: logika backendu (patrz
[[13-spec-backend-api]]).

## Widoki (projekt wstępny)

1. **Graph View** — renderowanie struktury grafu przy użyciu **React
   Flow** (patrz „Zdecydowane” niżej), z podświetleniem aktualnie
   wykonywanego węzła dla trwających runów.
2. **Runs / History** — lista `thread_id` z datą, statusem
   (`running`/`completed`/`failed`/`waiting_for_review`), link do
   szczegółów.
3. **Run Detail** — `get_state_history` jako oś czasu kroków, umożliwiająca
   „time travel” (podgląd stanu na dowolnym checkpointcie).
4. **Review Queue** — lista transakcji `needs_review`
   ([[06-spec-categorization]]) z akcją potwierdzenia/korekty kategorii,
   wywołującą `POST /runs/{thread_id}/resume`.
5. **Manual Trigger** — przycisk „uruchom teraz” wywołujący `POST /runs`
   (przydatne do testowania bez czekania na cotygodniowy cron).

## Zależności

- [[13-spec-backend-api]] — jedyne źródło danych dla UI.
- [[06-spec-categorization]] — kontrakt danych dla Review Queue.
- Skill `init-frontend` do scaffoldowania (Next.js, TypeScript, Tailwind) i
  skill `dataviz` przy projektowaniu wykresów/breakdownów w UI.

## Zdecydowane

- Biblioteka komponentów: **shadcn/ui** (nie Mantine — patrz `CLAUDE.md`,
  "Confirmed tech stack decisions"). Po `npx shadcn@latest init` motyw
  projektu aplikuje się komendą `npx shadcn@latest apply --preset
  byZfcT1E0`.
- Biblioteka renderowania grafu: **React Flow** (pakiet `@xyflow/react` —
  nazwa `react-flow-renderer` jest przestarzała/zastąpiona). Wybrane nad
  Mermaid.js, ponieważ węzły to prawdziwe komponenty React — naturalne
  podświetlanie aktualnie wykonywanego węzła na żywo i natywna integracja
  z Tailwind/shadcn, kosztem dodatkowej pracy: `get_graph()` z LangGraph
  nie dostarcza współrzędnych x/y węzłów, więc potrzebna jest osobna
  biblioteka auto-layoutu (np. `dagre` lub `elkjs` — konkretny wybór do
  zweryfikowania względem aktualnej dokumentacji przy implementacji, nie
  z pamięci).

## Otwarte kwestie

- Czy UI wymaga jakiejkolwiek formy logowania lokalnego (np. prosty PIN),
  biorąc pod uwagę że pokazuje dane finansowe — powiązane z otwartą
  kwestią bezpieczeństwa w [[13-spec-backend-api]].

## Kryteria akceptacji / testy

- Manualny test w przeglądarce: graf renderuje się poprawnie, historia
  uruchomień się ładuje, Review Queue pozwala potwierdzić kategorię i
  wznowić graf.
- Testy komponentów (Vitest, zgodnie z `init-frontend`) dla Review Queue i
  Graph View.
- Weryfikacja zgodnie z zasadą z `CLAUDE.md`: „For UI or frontend changes,
  start the dev server and use the feature in a browser before reporting
  the task as complete” — zastosować przy faktycznej implementacji, nie
  na etapie spec.
