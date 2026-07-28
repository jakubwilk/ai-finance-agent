# PLAN

Plan wykonawczy dla dwóch niezależnych strumieni pracy: backendu/LangGraph
(Python) i UI (React). Oparty na specyfikacjach w `docs/00`–`docs/16` oraz
ustaleniach z `CLAUDE.md`. To jest kolejność/harmonogram pracy — nie
duplikuje treści specyfikacji, tylko do nich odsyła.

## Zależność między planami

Kamienie milowe Plan B 0–4 i 6 mogą powstawać równolegle z Planem A,
korzystając z mocka API (patrz Plan B, krok 1). Wyjątki:

- **Plan B krok 5 (Review Queue)** potrzebuje realnego kształtu danych z
  **Planu A kroku 6 (Categorization)**, żeby kolejka przeglądu odzwierciedlała
  faktyczny kontrakt `needs_review`.
- **Plan B krok 8 (weryfikacja w przeglądarce)** wymaga, żeby **Plan A krok
  13 (Backend API)** faktycznie działał — nie wystarczy mock.

---

## Plan A: Backend / LangGraph (Python)

_Checklisty: `[ ]` = do zrobienia, `[x]` = zrobione — odznaczać w miarę postępu._

0. [x] **Fundament** — scaffold repo (skille `langgraph-python-quickstart`,
   `langchain-dependencies`), lokalny PostgreSQL, migracje wg
   [`01-spec-data-model`](docs/01-spec-data-model.md), skrypt seedujący
   `data/local/*.json` → tabele `CATEGORIES`/`FIXED_COSTS` (patrz sekcja
   „Przechowywanie realnej zawartości” w tej specyfikacji).
   *Blokujące: brak — start od razu.*
   - [x] Scaffold `backend/` (uv, Python 3.12, `langchain`/`langgraph`/
     `pydantic-settings`, ruff+pytest), `config.py` (wszystkie znane
     zmienne z `.env.example`, bez wartości), oraz szkielet master grafu
     (`graph/master.py`) z węzłami-placeholderami i pełnym rozgałęzieniem
     1:1 z diagramem w [`11-spec-orchestration-scheduling`](docs/11-spec-orchestration-scheduling.md),
     pokryty testami (`tests/test_master_graph.py`).
   - [x] Lokalny PostgreSQL (Docker Compose, `backend/docker-compose.yml`,
     `postgres:17-alpine` + osobna baza `finance_agent_test`) + modele
     SQLAlchemy 2.0 (`db/models.py`) 1:1 z ERD, migracje Alembic (async
     template, `alembic/versions/…_initial_schema.py`), pokryte testami
     integracyjnymi (`tests/test_db_schema.py`: upgrade/downgrade na czystej
     bazie testowej, integralność FK, unikalność `(account_id,
     drive_file_id)`).
   - [x] Skrypt seedujący (`backend/scripts/seed_reference_data.py`):
     walidacja Pydantic, idempotentny upsert po nazwie (bezpieczny do
     wielokrotnego uruchamiania), jasny błąd przy koszcie stałym
     wskazującym na nieistniejącą kategorię. Testy na fixture'ach w
     `tests/test_seed_reference_data.py` (nigdy na realnych
     `data/local/*.json`). Uruchomiony też raz na realnych danych
     dev-owych — zweryfikowane wyłącznie liczbą wierszy, bez ujawniania
     treści.

1. [ ] **Ingestion** — [`02-spec-google-drive-ingestion`](docs/02-spec-google-drive-ingestion.md):
   monitoring folderów Drive, pobieranie plików, zapis do `STATEMENTS`.
   Autoryzacja: OAuth kontem osobistym użytkownika, zmienne
   `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`/`GOOGLE_OAUTH_REFRESH_TOKEN`
   — **zdecydowane**, blokujące nie ma.
   - [x] Prerequisity: **fetch-on-demand** dla pobranych PDF-ów (bez trwałej
     kopii lokalnej — Drive to jedyne źródło prawdy, `STATEMENTS` ma tylko
     `drive_file_id`/`checksum`), zdecydowane z użytkownikiem i
     udokumentowane w `docs/02`/`docs/15` (usunięty wolumen). Reference
     data `ACCOUNTS` uzupełniona o ten sam wzorzec co `CATEGORIES`/
     `FIXED_COSTS`: `data/local/accounts.json` + `accounts.example.json`,
     unikalność `account_type` (migracja Alembic), rozszerzony
     `seed_reference_data.py` (`upsert_accounts`), testy izolowane
     transakcyjnie (`tests/conftest.py`: SAVEPOINT per test, żeby testy się
     wzajemnie nie zanieczyszczały). Uruchomiony na realnej bazie dev —
     zweryfikowane wyłącznie liczbą wierszy.
   - [x] Klient Google Drive API (`subgraphs/ingestion/drive_client.py`):
     `GoogleDriveClient` (`list_new_files` z paginacją `nextPageToken`,
     `download_file` przez `MediaIoBaseDownload`) przyjmuje gotowy `service`
     w konstruktorze (testowalne bez mockowania `googleapiclient.discovery.build`),
     `build_credentials`/`build_drive_client` budują `Credentials`
     bezpośrednio z `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`/`_REFRESH_TOKEN`
     (scope `drive.readonly`), jasny błąd gdy brak. Testy w pełni
     zmockowane (`tests/test_drive_client.py`), zgodnie z
     [`16-spec-testing-strategy`](docs/16-spec-testing-strategy.md) — bez
     realnego wywołania Drive (wartości `GOOGLE_OAUTH_*` wciąż nieuzupełnione
     w `.env`, nie blokuje tego kroku).
   - [x] Subgraph `ingestion` (`list_new_files` → `dedupe_check` →
     `download` → `persist_metadata` → `update_sync_cursor`) skomponowany
     w miejsce dzisiejszego placeholdera w master grafie. Zrobione:
     `subgraphs/ingestion/{state,nodes,graph}.py` — 5 async node-factory
     (DI: `AsyncSession`/`GoogleDriveClient` wstrzykiwane, ten sam wzorzec
     co `_make_placeholder`), `IngestionState` nigdy nie niesie surowych
     bajtów PDF (tylko `checksum` po `download`), `update_sync_cursor`
     przesuwa `last_synced_at` po max `modified_time` ze wszystkich
     odkrytych plików (nie tylko po dedupe). Po drodze wyszły dwie realne
     luki, załatane: (1) `Statement.period_start/period_end/
     opening_balance/closing_balance` musiały stać się nullable — te pola
     zna dopiero `verification_pre_check` (czyta nagłówek/stopkę PDF), nie
     ingestion (migracja `4458fb7299a5`, `docs/01`/`docs/02` zaktualizowane);
     (2) `ACCOUNTS` dostało `last_synced_at` (mutowalny stan runtime, nie
     seedowany) — ta sama migracja. Zweryfikowane bezpośrednio na
     `langgraph==1.2.9`: graf z choć jednym async node'em rzuca czytelny
     `TypeError` na sync `.invoke()` — stąd `build_master_graph(*,
     ingestion_node=...)` z DI: domyślnie prawdziwy async subgraph
     (`_ingestion_node`), testy branchingu w `test_master_graph.py`
     wstrzykują placeholder i zostają sync/`.invoke()`. Testy:
     `test_ingestion_graph.py` (fake drive client, `db_session` fixture,
     real Postgres) — dedupe, pełny przebieg, zero-nowych-plików, podwójne
     uruchomienie, konto bez skonfigurowanego folder ID pomijane, błąd
     Drive nie jest połykany.

     **Korekta (na życzenie użytkownika):** folder ID *nie* jest daną
     seedowaną/kolumną w `ACCOUNTS` (odrzucone jako pierwsze podejście) —
     żyje w `.env` jako `GOOGLE_DRIVE_FOLDER_ID_PRIVATE`/
     `GOOGLE_DRIVE_FOLDER_ID_COMPANY` (ten sam wzorzec co
     `REPORT_RECIPIENT_EMAIL_PRIVATE`/`_COMPANY` z kroku 11), migracja
     `e215a6689507` usuwa tę kolumnę ponownie. `build_ingestion_graph`/
     `make_list_new_files` przyjmują wstrzykiwany
     `folder_ids_by_account_type: dict[str, str]` zamiast czytać kolumnę z
     DB; `_ingestion_node` w `master.py` buduje to mapowanie z `settings`.
     Potwierdzone też: ingestion zostaje **polling** (cron wg harmonogramu),
     nie realny Drive `watch()`/webhook — ten wymagałby publicznego HTTPS
     endpointu (krok 14, deployment) i odnawiania kanału co ~7 dni, co nie
     ma sensu przy skali „kilka PDF-ów tygodniowo”.

     **Druga korekta (na życzenie użytkownika): usunięty cały podział
     private/company.** Z konta firmowego użytkownik płaci wyłącznie
     podatki i przelewa resztę na prywatne — więc firmowe nie jest częścią
     tego systemu w ogóle, nie tylko wyłączone z analizy. `Account.account_type`
     (kolumna + `CheckConstraint`/`UniqueConstraint`) i `Report.account_id`
     usunięte (migracja `23df7ac4b4b4`) — `ACCOUNTS` trzyma teraz dokładnie
     jeden wiersz (`display_name`/`bank_name`/`last_synced_at`), bez
     "typu"; `Statement.account_id` zostaje (referencyjna integralność do
     tego jedynego wiersza). `GOOGLE_DRIVE_FOLDER_ID_PRIVATE`/`_COMPANY` i
     `REPORT_RECIPIENT_EMAIL_PRIVATE`/`_COMPANY` skolapsowane do pojedynczych
     `GOOGLE_DRIVE_FOLDER_ID`/`REPORT_RECIPIENT_EMAIL`; `build_ingestion_graph`/
     `make_list_new_files` przyjmują teraz pojedynczy `folder_id: str | None`
     zamiast słownika po `account_type`. `seed_reference_data.py` waliduje,
     że `accounts.json` ma co najwyżej jeden wpis. Poprawki objęły też
     `README.md`, `docs/00`, `docs/01`, `docs/02`, `docs/04`, `docs/05`,
     `docs/08`, `docs/09`, `docs/10`, `docs/11`, `docs/13`, `docs/15` —
     usunięte wszystkie "otwarte kwestie" dotyczące per-konto branchingu
     (raporty, inwestycje, orkiestracja, `POST /runs`), bo są teraz
     rozstrzygnięte (zawsze jedno konto). Frontend nietknięty — potwierdzone
     (3 agenty Explore), że `RunSummary`/`fixtures.ts` nie mają żadnej
     zależności od tego rozróżnienia poza kosmetycznymi przykładowymi
     `threadId` w mockach.

2. [x] **Verification — pre-check** — [`03-spec-statement-verification`](docs/03-spec-statement-verification.md):
   czytelność PDF, odczyt `period_start`/`period_end`, sprawdzenie
   duplikatów. Zrobione: `subgraphs/verification/{state,nodes,graph}.py` —
   3 węzły (`read_statement`, `check_duplicate`, `mark_result`), ten sam
   wzorzec DI co ingestion. **Korekta na podstawie realnego przykładu**
   (użytkownik dostarczył prawdziwy eksport PKO BP „Historia rachunku"):
   pierwotny plan zakładał odczyt salda początkowego/końcowego z
   nagłówka/stopki — tego pola w tym formacie **nie ma**. Realny format ma
   tylko tabelę „Zastosowane kryteria wyboru" (`Od dnia`/`Do dnia`, jawne,
   tanie) i „Saldo po transakcji" przy każdej linii transakcji. Stąd
   `period_start`/`period_end` zostają w pre-checku, ale
   `opening_balance`/`closing_balance` przesunięte do ekstrakcji (krok 3,
   `docs/04`) jako efekt uboczny parsowania pierwszego/ostatniego wiersza —
   `docs/01`/`docs/02`/`docs/03`/`docs/04` zaktualizowane. Nowa zależność:
   `pdfplumber` (zatwierdzone przez użytkownika, MIT, sprawdzone bezpośrednio
   na realnym pliku — `extract_tables()` daje dokładnie oczekiwany kształt
   `['Od dnia', '2026-06-29', 'Kwota min', '-']`). `read_statement` łapie
   każdy wyjątek z parsowania PDF-a (nie tylko brak tekstu) i traktuje jako
   `unreadable_pdf` — inaczej pojedynczy uszkodzony plik wywaliłby cały
   batch. Nowy `failure_reason`: `unparseable_period`. Duplikat sprawdzany
   tylko po pokrywającym się zakresie dat (nie po `(account_id,
   drive_file_id)` — to i tak niemożliwe dzięki unique constraint). Testy:
   `test_verification_graph.py` — czyste testy logiki parsowania (bez
   realnych bajtów PDF, żeby nie commitować przykładu użytkownika ani nie
   dodawać zależności do generowania PDF-ów) + testy integracyjne na
   `db_session` z wstrzykiwanym fake extractorem.

3. [x] **Extraction** — [`04-spec-transaction-extraction`](docs/04-spec-transaction-extraction.md):
   wzorzec `StatementParser` (strategy pattern) + parser generyczny jako
   fallback. Zrobione: `subgraphs/extraction/parsers/{base,layout_utils,
   pko_bp,generic}.py` + `subgraphs/extraction/{state,nodes,graph}.py` (2
   węzły: `parse_statement`, `persist_transactions`). `pdfplumber`
   (już dodany w kroku 2) wystarcza, ale inaczej niż w pre-checku —
   `extract_tables()` zwraca zero tabel na stronach z transakcjami (brak
   linii siatki), więc `PkoBpHistoriaRachunkuParser` parsuje przez
   `extract_words()` (pozycje x0/top), z `layout_utils.cluster_words_into_rows`
   (bankowo-agnostyczne) grupującym słowa w wiersze; nowa transakcja
   zaczyna się tylko gdy kolumna „Data operacji” pasuje do
   `\d{4}-\d{2}-\d{2}` (inaczej powtarzający się nagłówek strony
   fałszywie dopasowuje się jako transakcja — znalezione i naprawione
   podczas prototypowania na realnym przykładzie). `Opis` parsowany
   generycznie jako pary `etykieta : wartość` (12+ różnych `Typ transakcji`
   w jednym tygodniu — stała lista pól per typ byłaby krucha).
   **Decyzje z użytkownikiem**: `TRANSACTIONS.raw_details` (nowy `jsonb`,
   migracja `b870ab2d4d6b`) trzyma wszystko poza `description`/
   `counterparty` (Lokalizacja/Adres/Miasto/Kraj/Nr karty/Nr rachunku/
   Referencje/Identyfikator/Typ transakcji) — nic nie odrzucone, ale nic z
   tego nie ma własnej kolumny; `txn_date` = Data operacji (nie Data
   waluty). `derive_statement_balances` (opening/closing balance z
   pierwszej/ostatniej sparsowanej transakcji, patrz korekta w kroku 2)
   zaimplementowane w `persist_transactions`, status wyciągu zostaje
   `verified` (post-check, krok 4, zmienia na `processed`/`failed`).
   Testy: `test_extraction_graph.py` — parsery jednostkowo na ręcznie
   zbudowanych słownikach pozycji słów (bez realnych bajtów PDF, ten sam
   powód co w kroku 2) + integracyjne na `db_session`.

4. [x] **Verification — post-check** — [`03-spec-statement-verification`](docs/03-spec-statement-verification.md)
   (krok 4): pełna zgodność sald po ekstrakcji. Zrobione:
   `subgraphs/verification/post_check_{state,nodes,graph}.py` (osobne
   pliki obok pre-checku w tym samym pakiecie, docs/03 traktuje oba jako
   fazy jednego subgraphu `verification`) — 2 węzły:
   `check_balance_consistency`, `mark_result`. Bez `drive_client` — to
   czysta arytmetyka na bazie, żadnego dostępu do Drive/PDF. Rozstrzygnięta
   ostatnia otwarta kwestia z `docs/03`: tolerancja zaokrągleń = **0.01
   PLN** (przyjęta proponowana wartość domyślna). Nowy `failure_reason`:
   `no_transactions_extracted` — wyciąg `verified`, który z jakiegoś powodu
   nie wyprodukował żadnej transakcji (więc `opening_balance`/
   `closing_balance` zostały `NULL` po ekstrakcji) jawnie failuje zamiast
   być cicho pomijany. Status końcowy: `processed` (sukces) albo `failed`
   (`balance_mismatch`/`no_transactions_extracted`). Testy:
   `test_verification_post_check_graph.py` — zgodność, granica tolerancji
   (dokładnie 0.01 nadal przechodzi), rozbieżność powyżej tolerancji, brak
   wyekstrahowanych transakcji, zero wyciągów `verified`.

5. [x] **LLM integration — fundament** — [`12-spec-llm-integration-ollama`](docs/12-spec-llm-integration-ollama.md):
   klient, timeout/retry/fallback, przed kategoryzacją bo ta go konsumuje.
   **Korekta:** użytkownik potwierdził, że faktycznie używa **OVH AI
   Endpoints**, nie self-hosted Ollama — zweryfikowane na żywym katalogu
   (`https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models`, bez
   autoryzacji): serverless, **kompatybilne z OpenAI**, nie surowy
   protokół Ollama. Stąd `langchain_openai.ChatOpenAI` z niestandardowym
   `base_url`, nie `langchain-ollama`/`ChatOllama` (nowa zależność
   `langchain-openai`, zatwierdzona). Zmienne przemianowane
   `OLLAMA_BASE_URL`/`OLLAMA_MODEL_*`/`OLLAMA_API_KEY` →
   `OVH_AI_ENDPOINTS_BASE_URL`/`OVH_AI_ENDPOINTS_API_KEY`/
   `OVH_MODEL_CLASSIFICATION`/`_INVESTMENT`/`_REPORTING` (użytkownik
   uzupełnił wartości pod nowymi nazwami). Zrobione:
   `backend/src/finance_agent/llm/client.py` — `build_chat_model`
   (czytelny błąd nazywający brakującą zmienną, `timeout=60`,
   `max_retries=3` realizujące „timeout i retry z backoff” natywnie przez
   `langchain_openai`) + `build_classification_model`/
   `build_investment_model`/`build_reporting_model` jako gotowe wejście
   dla kroków 6/9/10. Tylko fundament (konstrukcja klienta) — logika
   zadaniowa i fallback specyficzny dla zadania zostają w tamtych krokach.
   Testy: `test_llm_client.py` — konstrukcja/wiring, bez realnego
   wywołania OVH API.

6. [x] **Categorization** — [`06-spec-categorization`](docs/06-spec-categorization.md):
   `rule_match` → `llm_classify` → `confidence_gate` → `interrupt()` do
   przeglądu człowieka → zapis. Pierwszy kamień milowy wymagający
   `langgraph-human-in-the-loop`. **Ważne — częściowe ukończenie, celowo:**
   subgraph w pełni zaimplementowany i przetestowany
   (`subgraphs/categorization/{state,nodes,graph}.py`, real `interrupt()`/
   `Command(resume=...)`), ale **nie podpięty do `master.py`** — czytanie
   skilli `langgraph-human-in-the-loop`/`langgraph-persistence` ujawniło,
   że `interrupt()` wymaga checkpointera i `graph.invoke()` zwraca się od
   razu po trafieniu na niego (nie blokuje) — wznowienie to osobne
   wywołanie `Command(resume=...)`, dokładnie jak Plan B krok 5 (Review
   Queue) już zakładał (`POST /runs/{thread_id}/resume` jako osobne
   żądanie, potencjalnie dni później). Żeby to działało end-to-end przez
   master graf, potrzebny jest checkpointer + schemat `thread_id` na
   poziomie master grafu — to dopiero krok 12. Zdecydowane z użytkownikiem:
   zbudować i przetestować subgraph teraz w pełni (własny
   `InMemorySaver`/`checkpointer` przekazywany przez wywołującego), ale
   podpięcie pod placeholder `CATEGORIZATION` odłożyć do kroku 12, zamiast
   zgadywać jego projekt teraz. Nowa tabela `CATEGORY_RULES` (migracja
   `79554ef36e38`) — słownik `rule_match`, auto-uczący się z potwierdzeń
   `human_review` (zdecydowane, było robocze założenie w docs/06). Próg
   pewności **0.85** (zdecydowane, bardziej konserwatywnie niż
   proponowane 0.7). `method="function_calling"` dla structured output —
   niezweryfikowane na żywym OVH, ma fallback (błąd → pewność 0.0 →
   `needs_review`, nie crash batcha). Testy: `test_categorization_graph.py`
   — prawdziwe przebiegi interrupt/resume przez `InMemorySaver`, bez
   realnego wywołania OVH API.

7. [ ] **Fixed costs reconciliation** — [`05-spec-fixed-costs`](docs/05-spec-fixed-costs.md):
   dopasowanie do okresu bieżącego wyciągu, flagowanie rozbieżności.

8. [ ] **Cashflow calculation** — [`07-spec-cashflow-calculation`](docs/07-spec-cashflow-calculation.md):
   agregacja, breakdown per kategoria, surplus, narastający miesiąc.

9. [ ] **Investment analysis** — [`08-spec-investment-analysis`](docs/08-spec-investment-analysis.md):
   `check_safety_buffer` → `assess_trend` → `generate_allocation_proposal`.
   *Blokujące: profil ryzyka użytkownika, lista dostępnych instrumentów
   inwestycyjnych, wielkość poduszki bezpieczeństwa — wszystkie jawnie
   otwarte w specyfikacji.*

10. [ ] **Reporting** — [`09-spec-reporting`](docs/09-spec-reporting.md):
    renderowanie treści raportu tygodniowego/miesięcznego (HTML).

11. [ ] **Email delivery** — [`10-spec-email-delivery`](docs/10-spec-email-delivery.md):
    wysyłka SMTP + ścieżka natychmiastowego alertu. Format zmiennych
    ustalony (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`,
    `REPORT_RECIPIENT_EMAIL_PRIVATE`/`REPORT_RECIPIENT_EMAIL_COMPANY`).
    *Blokujące: konkretne wartości — do uzupełnienia przez użytkownika w
    `.env`.*

12. [ ] **Master orchestration graph + scheduling** — [`11-spec-orchestration-scheduling`](docs/11-spec-orchestration-scheduling.md):
    złożenie subgraphów 1–11 w master `StateGraph`, checkpointer Postgres,
    schemat `thread_id`, cron tygodniowy, logika raportu miesięcznego.

13. [ ] **Backend API** — [`13-spec-backend-api`](docs/13-spec-backend-api.md):
    FastAPI opakowujący gotowy master graph, pełna tabela endpointów.
    *Uwaga: minimalny stub (`/health`, statyczny `/graph/structure`) można
    zbudować już w kroku 0, żeby odblokować Plan B — patrz sekcja
    „Zależność między planami” wyżej.*

14. [ ] **Deployment** — [`15-spec-deployment-coolify`](docs/15-spec-deployment-coolify.md):
    Dockerfile'y, serwisy `docker-compose`/Coolify, zmienne środowiskowe,
    strategia backupu Postgresa.

> Testy: każdy krok 1–13 ma własne „Kryteria akceptacji / testy” w swojej
> specyfikacji, zgodnie ze wspólną strategią z
> [`16-spec-testing-strategy`](docs/16-spec-testing-strategy.md) — brak
> osobnego kamienia milowego, testy są częścią każdego kroku (reguła
> „Every feature needs tests” z `CLAUDE.md`).

---

## Plan B: Frontend / UI (React)

_Checklisty: `[ ]` = do zrobienia, `[x]` = zrobione — odznaczać w miarę postępu._

0. [x] **Scaffold** — skill `init-frontend` (Next.js, TypeScript, Tailwind,
   Vitest), następnie shadcn/ui dokładnie wg ustalenia w `CLAUDE.md`:
   `npx shadcn@latest init` → `npx shadcn@latest apply --preset
   byZfcT1E0` → `npx shadcn@latest add <component>` w miarę potrzeb
   kolejnych widoków. Zrobione: `frontend/` (Next.js 16 App Router,
   TypeScript, Tailwind v4, ESLint+import+Prettier, lint-staged, Vitest),
   bez Mantine; shadcn/ui zainicjalizowane (Base UI) z presetem
   `byZfcT1E0` — konkretne komponenty (`shadcn add`) dopiero z kolejnymi
   widokami. Git hooks: repo-wide `pre-commit` (root
   `.pre-commit-config.yaml`) zamiast Husky — `ruff-check`/`ruff-format`
   dla `backend/`, `lint-staged` (eslint+prettier) dla `frontend/`,
   każdy odpalany tylko gdy commit dotyka odpowiedniego katalogu.

1. [x] **Klient API + warstwa mocków** — typowany klient zgodny 1:1 z tabelą
   endpointów w [`13-spec-backend-api`](docs/13-spec-backend-api.md),
   oparty na lokalnym mock/fixture serwerze, żeby praca nad UI nie czekała
   na Plan A krok 13. Po jego ukończeniu — przełączenie na realny base URL
   backendu. Zrobione: `frontend/src/modules/common/{models/api.ts,api/}`
   — `ApiClient` interfejs wspólny dla `client.ts` (realny fetch) i
   `mockClient.ts` (fixture'y, w tym dokładny mermaid master grafu z
   `11-spec-orchestration-scheduling`), przełącznik w `api/index.ts` przez
   `NEXT_PUBLIC_USE_MOCK_API` (domyślnie mock, bez potrzeby `.env`).
   Kształty `RunState`/`RunHistoryEntry` celowo luźno typowane
   (`MasterGraphState` w `backend/` to na razie szkielet) — do
   doprecyzowania przy Planie A kroku 13.

2. [x] **Graph View** — renderowanie struktury grafu przy użyciu **React
   Flow** (`@xyflow/react` — zdecydowane, patrz
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md)); wymaga osobnej
   biblioteki auto-layoutu (np. `dagre`/`elkjs`); podświetlenie aktualnie
   wykonywanego węzła dla trwających runów. Zrobione:
   `frontend/src/modules/graph/` (`GraphView` + `getLayoutedElements` na
   `@dagrejs/dagre`, wg oficjalnego przykładu reactflow.dev), route
   `/graph`. `GraphStructureResponse` rozszerzone o `nodes`/`edges`
   (obok `mermaid`) w `common/models/api.ts` — React Flow potrzebuje
   ustrukturyzowanych danych, nie samego tekstu mermaid; fixture 1:1 z
   diagramem `11-spec-orchestration-scheduling`. Podświetlanie
   aktualnego węzła: prop `activeNodeId` na `GraphView` (przetestowany),
   nie podłączony jeszcze do realnego runu — to naturalnie przyjdzie z
   Run Detail (krok 4), gdzie `next` z historii faktycznie to mówi.

3. [x] **Runs / History** — lista `GET /runs` z odznakami statusu.
   Zrobione: `frontend/src/modules/runs/` (`RunStatusBadge` — pierwsze
   użycie shadcn `Badge`/`Table`; `RunsPage`, ten sam wzorzec
   loading/error/success co `GraphPage`), route `/runs`, posortowane po
   `createdAt` malejąco, link „Details" → `/runs/[threadId]` (404 do
   czasu kroku 4 — oczekiwane). Dodałem stały pasek nawigacji
   (`common/components/AppNav.tsx`, Graph | Runs) w `app/layout.tsx`,
   żeby `/runs` (i `/graph`) było osiągalne bez znajomości URL-a.

4. [x] **Run Detail (time travel)** — `GET /runs/{thread_id}/history` jako oś
   czasu kroków z podglądem stanu na dowolnym checkpointcie. Zrobione:
   route `/runs/[threadId]` (Next 16: `params` to `Promise`, `await`
   w cienkim server page, string dalej do `RunDetailPage`);
   `RunDetailPage` — klikalna oś czasu (jawnie posortowana po `step`,
   bo `get_state_history` realnie zwraca najnowszy checkpoint pierwszy),
   domyślnie wybrany najnowszy, panel stanu (JSON) + `next` węzeł(y).
   `GraphView`'s `activeNodeId` → `activeNodeIds: string[]` (LangGraph
   `next` to tablica, `Send`/równoległe gałęzie) i przeniesiony razem z
   `getLayoutedElements` z `modules/graph/` do `modules/common/` — teraz
   współdzielony przez `graph` i `runs`, zgodnie z regułą granic modułów.

5. [ ] **Review Queue** — lista transakcji `needs_review` (kontrakt danych z
   [`06-spec-categorization`](docs/06-spec-categorization.md) i
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md)), akcja
   potwierdzenia/korekty wywołująca `POST /runs/{thread_id}/resume`.
   *Zależy od Planu A kroku 6 (Categorization) — realny kształt danych.*

6. [x] **Manual Trigger** — przycisk „uruchom teraz” wywołujący `POST /runs`.
   Zrobione: `modules/runs/components/TriggerRunButton.tsx` (pierwsze
   użycie shadcn `Button`) na `RunsPage`, obok nagłówka. `mockClient`
   (`common/api/mockClient.ts`) stał się stanowy dla runów (`listRuns`
   czyta z tego, co dopisał `triggerRun`) — wierniej odzwierciedla
   realny backend (`POST` → `GET` pokazuje nowy wpis) niż statyczny
   fixture; `resetMockRuns()` (test-only) trzyma testy deterministycznymi.

7. [ ] **Wykresy / breakdowny** — zastosowanie skilla `dataviz` do breakdownów
   kategorii i trendów w Graph View / Run Detail.

8. [ ] **Weryfikacja** — testy komponentów (Vitest) dla Review Queue i Graph
   View wg kryteriów w
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md); następnie
   uruchomienie dev servera i przetestowanie golden path + edge case'ów w
   przeglądarce na realnym backendzie, zgodnie z zasadą z `CLAUDE.md` dla
   zmian UI. Wykonać dopiero, gdy Plan A krok 13 (Backend API) faktycznie
   działa — nie na mocku.

---

## Otwarte kwestie blokujące poszczególne kroki

Zebrane w jednym miejscu z linkami do specyfikacji źródłowych — do
rozstrzygnięcia z użytkownikiem przed startem odpowiedniego kroku, nigdy
nie zakładane. (Autoryzacja Drive i biblioteka Graph View zostały już
rozstrzygnięte — patrz odpowiednie specyfikacje — i nie figurują tu
dłużej.)

| Otwarta kwestia | Blokuje | Specyfikacja |
|---|---|---|
| Profil ryzyka, lista instrumentów inwestycyjnych, wielkość poduszki bezpieczeństwa | Plan A krok 9 | [`08-spec-investment-analysis`](docs/08-spec-investment-analysis.md) |
| Konkretne wartości SMTP i adresów odbiorców (format zmiennych już ustalony) | Plan A krok 11 | [`10-spec-email-delivery`](docs/10-spec-email-delivery.md) |
