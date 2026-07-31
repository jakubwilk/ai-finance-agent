# 13 — Backend API

## Cel

Wystawić lokalny FastAPI backend jako jedyny pośrednik między React UI a
master grafem LangGraph — bez jakiegokolwiek konta chmurowego
(LangSmith/LangGraph Studio wykluczone zgodnie z decyzją w `CLAUDE.md`).

## Zakres

Wchodzi: endpointy do triggerowania runów, listy wątków, historii stanu,
struktury grafu, health-checki. Nie wchodzi: logika samego pipeline'u
(patrz [[11-spec-orchestration-scheduling]]) ani UI (patrz
[[14-spec-frontend-ui]]).

## Endpointy (zaimplementowane, Plan A krok 13)

Kontrakt 1:1 z już istniejącym `frontend/src/modules/common/models/api.ts`/
`api/client.ts` (Plan B krok 1, zbudowany wcześniej niezależnie na mocku) —
JSON w camelCase (`pydantic.alias_generators.to_camel`,
`response_model_by_alias=True` domyślnie w FastAPI, zweryfikowane na
zainstalowanej wersji).

| Metoda | Ścieżka | Cel |
|---|---|---|
| `GET` | `/graph/structure` | `build_master_graph().get_graph()` → mermaid + `nodes`/`edges` ustrukturyzowane (`Node(id, name, data, metadata)`/`Edge(source, target, data, conditional)`, zweryfikowane na realnym grafie). `categorization` oznaczony `kind="interrupt"` (przegląd człowieka żyje wewnątrz niego, patrz [[11-spec-orchestration-scheduling]]'s korekta z kroku 12), `alert_immediate` — `kind="alert"`. |
| `GET` | `/categories` | **Dodane poza pierwotną tabelą** — konsumowane przez `ApiClient.getCategories()` frontendu (Review Queue), bez tego nie ma z czego zbudować dropdowna kategorii. |
| `POST` | `/runs` | Nowy `thread_id` (`manual-{uuid4}`, osobny od cotygodniowego `generate_weekly_thread_id()`), wiersz `RUNS` zapisany synchronicznie (status `running`), realny przebieg master grafu odpalony w tle (`BackgroundTasks`) — odpowiedź wraca natychmiast. |
| `GET` | `/runs` | `SELECT * FROM runs ORDER BY created_at DESC` — **nowa tabela `RUNS`**, patrz „Realne odkrycie" niżej. |
| `GET` | `/runs/{thread_id}/state` | `aget_state(config)` na master grafie z realnym checkpointerem → `values` + `pendingReviews` (zdekodowane z `StateSnapshot.interrupts[].value["pending_reviews"]`, kształt zweryfikowany przez introspekcję zainstalowanego `langgraph`). 404 gdy `created_at is None` (nieznany `thread_id`, też zweryfikowane empirycznie). |
| `GET` | `/runs/{thread_id}/history` | `aget_state_history(config)` → lista `{checkpointId, step, values, next, createdAt}`. 404 gdy pusta historia. |
| `POST` | `/runs/{thread_id}/resume` | body `{"resume": <cokolwiek>}` — wznowienie po `interrupt()` (`Command(resume=...)`), używane przez `human_review` w [[06-spec-categorization]]. `RUNS` status → `running` synchronicznie, realny przebieg w tle, odpowiedź zwraca bieżący stan (eventual consistency — frontend może odpytać `/state` ponownie). 404 gdy `thread_id` nieznany w `RUNS`. |
| `GET` | `/runs/{thread_id}/cashflow` | Odczyt persystowanego wyniku subgrafu `cashflow_calculation` z nowej tabeli `CASHFLOW_SUMMARIES` (`thread_id` PK) — patrz „Realne odkrycie" niżej. 404 gdy brak wiersza dla `thread_id`, ten sam wzorzec co `/state`/`/history`. |
| `DELETE` | `/runs/{thread_id}` | Usuwa wiersz `RUNS` i historię checkpointera dla wątku — patrz „`DELETE /runs/{thread_id}`" niżej. 204 bez treści przy sukcesie, 404 gdy nieznany `thread_id`, 409 gdy run ma status `running`. |
| `GET` | `/health` | `database`: `SELECT 1`; `ollama` (nazwa pola zostaje taka w kontrakcie mimo że realnie to OVH AI Endpoints od kroku 5 — zmiana JSON-a złamałaby już zbudowany frontend bez korzyści): lekki `GET /models` na `OVH_AI_ENDPOINTS_BASE_URL` (ten sam publicznie osiągalny katalog zweryfikowany w kroku 5). `status`: `ok` (oba) / `degraded` (jedno) / `down` (żadne). |

**Realne odkrycie przy implementacji:** checkpointer LangGraph nie ma API
"wylistuj wszystkie `thread_id`" (sprawdzone w źródłach/forum LangGraph —
`checkpointer.list()` wymaga już znanego `thread_id`) i nie reprezentuje
stanu `failed` (nieobsłużony wyjątek nie tworzy checkpointa). Stąd nowa,
lekka tabela domenowa `RUNS` (`thread_id` PK, `status`, `created_at`,
`updated_at`), aktualizowana przez `run_master_graph`
(`graph/runner.py`'s `upsert_run_status`) — celowo osobna od tabel
checkpointera (`checkpoints`/`checkpoint_writes`, zarządzanych wyłącznie
przez `langgraph-checkpoint-postgres`, patrz [[01-spec-data-model]]).

## `GET /runs/{thread_id}/cashflow` — persystencja wyniku `cashflow_calculation`

Frontend (Plan B krok 7) ma gotowy panel (`CashflowSummaryPanel`,
`CategoryBreakdownChart`) i pełny typowany kontrakt
(`frontend/src/modules/common/models/api.ts`'s `CashflowSummary`), dziś
podpięty realnie do `client.ts`'s `getCashflowSummary(threadId)`.

- **Realne odkrycie przy implementacji:** `graph/master.py`'s
  `_cashflow_calculation_node` odpalał subgraf `cashflow_calculation`, ale
  odrzucał jego wynik — zwracał tylko
  `{"visited": ["cashflow_calculation"]}`. Gorzej: **nie istniało żadne
  powiązanie `thread_id → statement_id`** w żadnej tabeli (`RUNS` ma tylko
  `thread_id`/`status`; `Statement` nie ma kolumny `thread_id`), a sam
  subgraf zawsze sam wybiera "najnowszy przetworzony wyciąg" z bazy
  (`_current_statement()` w `subgraphs/cashflow/nodes.py`), ignorując
  cokolwiek podane na wejściu. To wykluczyło wariant "przelicz on-demand
  dla tego wątku" bez dodatkowych zmian — bez zapisanego powiązania,
  przeliczenie dla starego/historycznego `thread_id` zwróciłoby dane
  najnowszego przetworzonego wyciągu, niekoniecznie tego samego, który
  przetworzył ten konkretny run.
- **Rozwiązanie:** nowa, lekka tabela domenowa `CASHFLOW_SUMMARIES`
  (`thread_id` PK/FK→`runs.thread_id`, `statement_id`, `weekly`,
  `rolling_month`, `fixed_costs_status` jako JSONB, `computed_at`) — ten
  sam wzorzec co `RUNS`. `_cashflow_calculation_node` zyskał `config:
  RunnableConfig` (odczyt `thread_id`) i przestał odrzucać wynik
  `cashflow_graph.ainvoke(...)` — zapisuje go przez
  `_upsert_cashflow_summary`.
- **Response 200** — Pydantic `CamelModel` odzwierciedlający
  `subgraphs/cashflow/state.py`'s `CashflowState`/`PeriodSummary`/
  `CategoryBreakdownEntry`/`FixedCostStatusEntry` 1:1, camelCase JSON
  zgodny z frontendowym `CashflowSummary` pole po polu:
  `statementId: str | None`, `weekly`/`rollingMonth`:
  `PeriodSummary | None` (`periodStart`, `periodEnd`, `totalIncome`,
  `totalExpense`, `categoryBreakdown`, `needsReviewCount`, `surplus`),
  `fixedCostsStatus: list[FixedCostStatusEntry]`. `total`/`totalIncome`/
  `totalExpense`/`surplus` to podpisane decimal **stringi** (nie floaty),
  jak wszędzie indziej w tym API. `categoryBreakdown` obejmuje wszystkie
  transakcje okresu (przychody i wydatki), stąd znak; wpis
  `categoryId: null` / `categoryName: "Nieskategoryzowane"` to transakcje
  bez kategorii. `weekly`/`rollingMonth` bywają `null`, gdy run jeszcze nie
  doszedł do `cashflow_calculation`.
- **Errors**: `404 {"detail": f"Unknown thread_id: {thread_id}"}` dla
  nieznanego `thread_id` — ten sam wzorzec co `get_run_state`/
  `get_run_history`.

## `DELETE /runs/{thread_id}`

- **Cel / kontekst**: użytkownik chce móc usuwać zbędne/testowe/nieudane
  wpisy z listy runów w UI (`RunsPage.tsx`, `DeleteRunButton.tsx`).
- **Request**: `DELETE /runs/{thread_id}`, ten sam `require_api_key` co
  wszystkie inne endpointy.
- **Response**: `204 No Content` przy sukcesie — bez body, frontend po
  prostu usuwa wiersz lokalnie po otrzymaniu 2xx.
- **Errors**: `404 {"detail": f"Unknown thread_id: {thread_id}"}` dla
  nieznanego `thread_id`, ten sam wzorzec co `get_run_state`/
  `get_run_history`/`get_run_cashflow`. `409
  {"detail": f"Cannot delete run in progress: {thread_id}"}` gdy run ma
  status `running`.
- **Rozstrzygnięcia trzech otwartych pytań z poprzedniej wersji tego
  dokumentu** (wszystkie zweryfikowane bezpośrednio, nie zgadywane):
  1. **FK bez cascade** — `cashflow_summaries.thread_id → runs.thread_id`
     (`alembic/versions/3a350f20997d_...py`) nie miało `ON DELETE
     CASCADE`; potwierdzone bezpośrednio w bazie, że constraint nazywa się
     `cashflow_summaries_thread_id_fkey`. Nowa migracja
     (`c4cca31cd988_cashflow_summaries_cascade_delete.py`) odtwarza go z
     `ondelete="CASCADE"` — usunięcie `runs` automatycznie usuwa powiązany
     `cashflow_summaries`, bez ręcznego dwuetapowego DELETE w kodzie.
  2. **Tabele checkpointera** — `AsyncPostgresSaver`/`InMemorySaver` (na
     zainstalowanej wersji `langgraph-checkpoint-postgres`) mają realną
     metodę `adelete_thread(thread_id)`, która usuwa wszystkie checkpointy
     i zapisy dla danego wątku. `delete_run` woła ją przed usunięciem
     wiersza `runs` — pełne czyszczenie historii, bez ręcznego SQL.
  3. **Blokada dla `status == "running"`** — przyjęty sugerowany bezpieczny
     domyślny wybór: zablokowane, `409 Conflict`. Powód: `BackgroundTasks`
     może wciąż wykonywać `run_master_graph` dla tego `thread_id`;
     usunięcie wiersza `runs` w międzyczasie złamałoby FK przy próbie
     zapisu `cashflow_summaries` przez wciąż działający graf.

## Zależności

- [[11-spec-orchestration-scheduling]] — master graph, którym ten backend
  steruje.
- [[06-spec-categorization]] — `resume` obsługuje decyzje human-in-the-loop.
- [[14-spec-frontend-ui]] — konsument tego API.
- [[01-spec-data-model]] — odczyt danych domenowych do wzbogacenia
  odpowiedzi (np. podgląd transakcji `needs_review`).

## Bezpieczeństwo

Backend nie jest wystawiony publicznie bez uwierzytelnienia — dostęp tylko
z sieci lokalnej/wewnętrznej Coolify **oraz** prosty API key.
**Zdecydowane z użytkownikiem:** jeden statyczny klucz w `.env`
(`BACKEND_API_KEY`), sprawdzany na **każdym** żądaniu (w tym `/health` —
dane finansowe wrażliwe, brak wyjątków) przez `require_api_key`
(`api/dependencies.py`), nagłówek `X-API-Key`. Identyczny `401` dla
"nieskonfigurowany klucz" i "zły klucz" — nigdy nie ujawniać stanu
konfiguracji serwera nieuwierzytelnionemu wywołującemu. Dane finansowe
wrażliwe → żadnych sekretów (SMTP, Drive, DB) w odpowiedziach API (żaden z
powyższych endpointów ich nie zwraca).

## Otwarte kwestie

Rozstrzygnięte z użytkownikiem przy implementacji — patrz „Bezpieczeństwo”
wyżej.

## Kryteria akceptacji / testy

- Test `GET /graph/structure` zwraca poprawny Mermaid, renderowalny bez
  błędów w UI — zrobione (`tests/test_api.py`).
- Test `POST /runs` → `GET /runs/{thread_id}/state` pokazuje postęp
  uruchomienia — zrobione (`test_trigger_run_is_immediately_listed`).
- Test `resume` po `interrupt()` poprawnie wznawia zawieszony graf —
  zrobione na poziomie `run_master_graph`
  (`tests/test_runs_repository.py`, z prawdziwym `interrupt()`/
  `Command(resume=...)` przez `InMemorySaver`) i na poziomie HTTP
  (`tests/test_api.py`, z podmienionym `trigger` — nie duplikuje tamtego
  pokrycia, tylko sprawdza że endpoint poprawnie woła `get_run_trigger()`
  i aktualizuje `RUNS`).
- Test `/health` poprawnie raportuje niedostępność bazy/Ollama gdy są
  wyłączone — zrobione dla `database` (przez `dependency_overrides` na
  bazę testową); `ollama`/OVH nie jest osobno testowane jako "wyłączone"
  (wymagałoby mockowania `httpx`) — pokryte tylko happy-path (`status in
  {ok, degraded, down}`).
- Test uwierzytelnienia (`X-API-Key` brak/zły/poprawny) — zrobione
  (`tests/test_api.py`), nie było w pierwotnych kryteriach bo otwarta
  kwestia dopiero się rozstrzygnęła.
- Test `GET /runs/{thread_id}/cashflow`: 404 dla nieznanego `thread_id`,
  200 z poprawnym camelCase kształtem dla persystowanego wiersza — zrobione
  (`tests/test_api.py`). `_upsert_cashflow_summary`'s create-then-update
  upsert — zrobione osobno (`tests/test_cashflow_summary_persistence.py`).
- Test `DELETE /runs/{thread_id}`: 404 dla nieznanego `thread_id`, 409 dla
  `status="running"` (wiersz `runs` przetrwał), 204 dla `status="completed"`
  z usunięciem obu wierszy (`runs` + cascade `cashflow_summaries`) i
  wywołaniem `checkpointer.adelete_thread` z poprawnym `thread_id` —
  zrobione (`tests/test_api.py`).
