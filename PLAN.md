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

7. [x] **Fixed costs reconciliation** — [`05-spec-fixed-costs`](docs/05-spec-fixed-costs.md):
   dopasowanie do okresu bieżącego wyciągu, flagowanie rozbieżności. Zrobione:
   `subgraphs/fixed_costs/{state,nodes,graph}.py` — 4 węzły (`load_fixed_costs`,
   `match_transactions`, `flag_discrepancies`, `persist_reconciliation`), ten
   sam wzorzec DI co pozostałe subgrafy, bez `drive_client` (czysta logika
   DB). **Decyzje z użytkownikiem** (docs/05 miało to jawnie otwarte): sygnał
   dopasowania to `Transaction.category_id == FixedCost.category_id`
   (kategoryzacja działa zawsze przed tym krokiem), nie fuzzy-matching po
   kontrahencie/opisie; tolerancja kwoty **5% `expected_amount`**, stała w
   kodzie (`AMOUNT_TOLERANCE_RATIO`), nie parametr konfiguracyjny; „bieżący
   wyciąg” = pojedynczy `Statement` o najpóźniejszym `period_end` wśród
   `status == "processed"` (jedno konto, wyciągi tygodniowe). Doprecyzowanie
   przy implementacji: tolerancja decyduje o klasyfikacji rozbieżności
   (`matched` vs `amount_changed`), nie o tym, czy dopasowanie w ogóle
   istnieje — inaczej transakcja o mocno zmienionej kwocie nigdy nie
   zostałaby powiązana ze swoim kosztem stałym i błędnie wyglądałaby jak
   `missing_payment`. Nowa kolumna `TRANSACTIONS.matched_fixed_cost_id`
   (nullable FK do `fixed_costs.id`, migracja `eccfb86a2bf4`) — jedyna
   trwała dana z reconciliation; sama lista rozbieżności jest efemeryczna
   (zwracana przez subgraph, konsumowana w tym samym przebiegu master grafu
   przez kroki 8/10, jeszcze niezaimplementowane), bez osobnej tabeli — nie
   ma jeszcze czytelnika, który wymagałby jej trwałości. W przeciwieństwie do
   `categorization` (krok 6, celowo niepodpięty — czeka na checkpointer z
   kroku 12), ten krok nie ma `interrupt()`/human-in-the-loop, więc
   `fixed_costs_reconciliation` **jest już podpięty** do `master.py`
   (`_fixed_costs_reconciliation_node`, ten sam kształt
   sesja/commit-lub-rollback co `_verification_post_check_node`), wyjęty z
   pętli placeholderów. Testy: `tests/test_fixed_costs_graph.py` — dopasowanie
   w tolerancji, `missing_payment` (brak kandydata w kategorii),
   `amount_changed` (dopasowany, ale poza tolerancją, `matched_fixed_cost_id`
   mimo to ustawione), pusta tabela `FIXED_COSTS` (no-op), brak wyciągu
   `processed` (no-op), dwa koszty stałe w jednej kategorii dopasowane do
   różnych transakcji (brak podwójnego przypisania). `tests/test_master_graph.py`
   zaktualizowany o wstrzykiwany placeholder dla nowego realnego węzła w
   testach behawioralnych (sync `.invoke()`).

8. [x] **Cashflow calculation** — [`07-spec-cashflow-calculation`](docs/07-spec-cashflow-calculation.md):
   agregacja, breakdown per kategoria, surplus, narastający miesiąc. Zrobione:
   `subgraphs/cashflow/{state,nodes,graph}.py` — 5 węzłów
   (`aggregate_income_expense`, `breakdown_by_category`,
   `apply_fixed_costs_status`, `compute_surplus`, `compute_rolling_month`),
   ten sam wzorzec DI co pozostałe subgrafy, bez `drive_client`.
   **Decyzje z użytkownikiem** (docs/07 miało to jawnie otwarte):
   transakcje `needs_review` **wliczone** do bilansu wg tymczasowej kategorii
   z LLM, z osobnym `needs_review_count` do ostrzeżenia w przyszłym raporcie
   (krok 10); „bieżący wyciąg" = ten sam koncept co w kroku 7 (najpóźniejszy
   `Statement.period_end` wśród `status == "processed"`), nie ISO tydzień
   kalendarzowy. `apply_fixed_costs_status` **nie** powtarza dopasowania z
   kroku 7 — czyta już zapisane `Transaction.matched_fixed_cost_id`, tylko
   klasyfikuje `matched`/`amount_changed` tą samą stałą tolerancji
   `AMOUNT_TOLERANCE_RATIO` (reużyta z `subgraphs/fixed_costs/nodes.py`, nie
   zduplikowana). `compute_rolling_month` liczy narastająco od pierwszego
   dnia miesiąca `Statement.period_end` do tego `period_end`, po
   `Transaction.txn_date` przez wszystkie wyciągi `processed` w tym
   miesiącu (nie tylko bieżący) — bez zależności od zegara systemowego
   (`datetime.now()`), spójne z resztą pipeline'u. Ten sam wzorzec co krok 7:
   wynik efemeryczny (zwracany przez subgraph, konsumowany w tym samym
   przebiegu master grafu przez kroki 9/10, jeszcze niezaimplementowane),
   bez osobnej tabeli — nie ma jeszcze czytelnika, który wymagałby jej
   trwałości. Bez `interrupt()`/human-in-the-loop, więc
   `cashflow_calculation` **jest już podpięty** do `master.py`
   (`_cashflow_calculation_node`, ten sam kształt sesja/commit-lub-rollback
   co pozostałe realne węzły), wyjęty z pętli placeholderów. Testy:
   `tests/test_cashflow_graph.py` — sumy przychodów/wydatków, breakdown per
   kategoria (w tym `Nieskategoryzowane`, nic nie ginie z sumy), wliczenie i
   zliczenie `needs_review`, wszystkie 3 statusy kosztów stałych, surplus,
   narastający miesiąc na dwóch wyciągach (weekly widzi tylko bieżący,
   rolling_month oba), brak wyciągu `processed` (no-op). `tests/test_master_graph.py`
   zaktualizowany o wstrzykiwany placeholder dla nowego realnego węzła w
   testach behawioralnych (sync `.invoke()`).

9. [x] **Investment analysis** — [`08-spec-investment-analysis`](docs/08-spec-investment-analysis.md):
   `check_safety_buffer` → `assess_trend` → `generate_allocation_proposal` →
   `persist_recommendation`. Było blokujące (profil ryzyka, instrumenty,
   poduszka bezpieczeństwa) — **rozstrzygnięte z użytkownikiem**: profil
   zbalansowany; instrumenty ETF/lokaty/konto oszczędnościowe (nie obligacje
   skarbowe, nie IKE/IKZE); poduszka jako stała kwota PLN; agent wyłącznie
   sugeruje (jawna decyzja bezpieczeństwa, zero integracji z API
   maklerskim/bankowym). Zrobione:
   `subgraphs/investment/{state,nodes,graph}.py` — 4 węzły, ten sam wzorzec
   DI co pozostałe subgrafy. **Dwie realne luki w schemacie**, załatane po
   drodze: (1) brak trwałego miejsca na profil ryzyka/poduszkę/instrumenty —
   nowa tabela `INVESTMENT_SETTINGS` (pojedynczy wiersz, ten sam wzorzec co
   `ACCOUNTS`), realna zawartość w gitignorowanym
   `data/local/investment_settings.json` (`.example.json` skomitowany),
   `seed_reference_data.py` rozszerzony o `upsert_investment_settings`;
   (2) `INVESTMENT_RECOMMENDATIONS.report_id` było `NOT NULL`, ale
   `investment_analysis` biegnie przed `reporting` w master grafie — kolumna
   stała się nullable (migracja `0634c426bfc5`), `persist_recommendation`
   zapisuje z `report_id=NULL`, krok 10 uzupełni później (ten sam wzorzec co
   nullable pola `Statement` z kroku 1). W przeciwieństwie do kroków 7/8
   (efemeryczny wynik, brak czytelnika) — `INVESTMENT_RECOMMENDATIONS` ma
   dedykowaną tabelę od kroku 0, więc zapis do bazy jest tu poprawny, nie
   przedwczesny. `check_safety_buffer`: `investable_amount = min(surplus,
   max(closing_balance - safety_buffer_amount, 0))`, zero gdy surplus ≤ 0
   (bez wywołania LLM). `assess_trend`: `TREND_LOOKBACK_PERIODS = 4`,
   `ANOMALY_MULTIPLIER = 2` (dobór implementacyjny — spec nie precyzowała
   liczby, tylko „kilka ostatnich okresów”); mniej niż 2 wyciągi w historii →
   `insufficient_history`, brak korekty. `generate_allocation_proposal`:
   `chat_model.with_structured_output(AllocationResult,
   method="function_calling")` ze stałym schematem (nie dynamiczny słownik —
   bezpieczniej dla function-calling), fallback na równy podział przy
   błędzie LLM/nieprawidłowej sumie procentów (ten sam „nie wywalaj batcha”
   wzorzec co `categorization`'s `llm_classify`). Mały refaktor przy okazji:
   `compute_income_and_expense` wydzielone z `subgraphs/cashflow/nodes.py`
   (było zduplikowane między `aggregate_income_expense`/
   `compute_rolling_month`), reużyte też tutaj — ten sam wzorzec
   cross-subgraph reuse co `AMOUNT_TOLERANCE_RATIO`. Bez `interrupt()`, więc
   `investment_analysis` **jest już podpięty** do `master.py`, wyjęty z
   pętli placeholderów. Testy: `tests/test_investment_graph.py` — poduszka
   wiążąca/niewiążąca, surplus ≤ 0 pomija LLM, anomalia ogranicza kwotę do
   średniej historycznej, `insufficient_history`, prawidłowy podział z LLM,
   fallback przy błędzie LLM, brak `InvestmentSettings` (no-op), zapis
   rekomendacji z `report_id=NULL`. `tests/test_master_graph.py`/
   `tests/test_db_schema.py`/`tests/test_seed_reference_data.py`
   zaktualizowane.

10. [x] **Reporting** — [`09-spec-reporting`](docs/09-spec-reporting.md):
    renderowanie treści raportu tygodniowego/miesięcznego (HTML). Zrobione:
    `subgraphs/reporting/{state,nodes,graph}.py` + `templates/{weekly,monthly}.html.jinja`
    — 4 węzły, ten sam wzorzec DI co pozostałe subgrafy. **Decyzje z
    użytkownikiem** (docs/09 miało to jawnie otwarte): wizualizacja jako
    same tabele HTML (bez pasków CSS/wykresów — najbezpieczniejsze między
    klientami mailowymi); dodana nowa zależność **Jinja2** (`uv add jinja2`,
    zatwierdzona przed dodaniem, ten sam tryb co `pdfplumber`/
    `langchain-openai` wcześniej). Język raportu: polski, potwierdzone przez
    istniejącą konwencję (nie trzeba było pytać ponownie). **Realny problem
    architektoniczny rozwiązany:** kroki 08/09 (cashflow/investment)
    celowo zostawiły swój wynik efemerycznym (brak czytelnika w momencie
    ich implementacji) — `render_weekly` odzyskuje te dane wywołując
    `build_cashflow_graph(session).ainvoke(...)` bezpośrednio (ten sam
    subgraph co krok 08, użyty jako czarna skrzynka, nie zduplikowana
    logika — tanie, bo to czysta arytmetyka bez zapisów) i odczytując
    najnowszy `INVESTMENT_RECOMMENDATIONS` z `report_id IS NULL`.
    Odrzucona alternatywa: przepływ danych przez `MasterGraphState` — byłby
    niespójny z resztą repo (każdy subgraph sam odtwarza swoje wejście z
    bazy). `persist_report` zamyka pętlę z kroku 09: uzupełnia
    `INVESTMENT_RECOMMENDATIONS.report_id` (nullable od tamtego kroku) na
    wiersz raportu tygodniowego — **znane, zaakceptowane ograniczenie**:
    jeśli reporting zawiedzie w danym tygodniu, tylko najnowsza
    niepodłączona rekomendacja zostaje podłączona następnym razem, starsze
    osierocone zostają z `report_id = NULL` na stałe (brak utraty danych,
    tylko niekompletne powiązanie). „Koniec miesiąca” zdecydowany jako
    `period_end` w ostatnich 7 dniach swojego miesiąca
    (`MONTH_END_WINDOW_DAYS`, implementacyjny dobór jak
    `TREND_LOOKBACK_PERIODS`/`ANOMALY_MULTIPLIER` z kroku 09 — spec nie
    precyzowała dokładnego testu). Porównanie z poprzednim miesiącem: jedyne
    naprawdę nowe zapytanie w tym kroku, reużywa `compute_income_and_expense`
    z `cashflow/nodes.py` (ten sam wzorzec cross-subgraph reuse co
    `AMOUNT_TOLERANCE_RATIO`). Bez `interrupt()`, więc `reporting` **jest już
    podpięty** do `master.py`, wyjęty z pętli placeholderów. `build_reporting_model()`
    (zbudowany w kroku 05) zostaje nieużyty — nic w spec nie wymaga
    reasoningu LLM na tym etapie, tylko wypełnianie szablonu; dostępny na
    przyszłość. Testy: `tests/test_reporting_graph.py` — treść raportu
    tygodniowego (sumy, breakdown), brak nadwyżki (bez rekomendacji i z
    rekomendacją o kwocie zero — oba pokazują komunikat), lista
    `needs_review` (obecna/pominięta), koniec miesiąca generuje dodatkowy
    raport z poprawnym porównaniem, środek miesiąca nie generuje raportu
    miesięcznego, zapis `REPORTS` + backfill `report_id`, brak wyciągu
    `processed` (no-op). `tests/test_master_graph.py` zaktualizowany.

11. [x] **Email delivery** — [`10-spec-email-delivery`](docs/10-spec-email-delivery.md):
    wysyłka SMTP + ścieżka natychmiastowego alertu. Format zmiennych już
    ustalony (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/
    `REPORT_RECIPIENT_EMAIL`, pojedyncze — bez podziału private/company,
    usuniętego w kroku 1). Oznaczone jako blokujące na realnych wartościach
    w `.env` — **ale sprawdzenie precedensu z kroków 1/5 (`GOOGLE_OAUTH_*`,
    `OVH_AI_ENDPOINTS_*` też puste, a te kroki i tak w pełni zbudowane i
    przetestowane z fake'ami) pokazało, że puste `.env` nie blokuje budowy
    ani testów — tylko realne uruchomienie.** Zrobione:
    `subgraphs/email_delivery/{smtp_client,state,nodes,graph}.py` — 3 węzły
    subgraphu (`render_final_payload`, `send_smtp`, `handle_result`) dla
    kolejki `REPORTS` `pending`, ten sam wzorzec DI co `GoogleDriveClient`
    (`SmtpClient` przyjmuje gotowe połączenie, `build_smtp_client(settings)`
    czytelny błąd przy brakującej zmiennej). **Nowa zależność, zatwierdzona:**
    `aiosmtplib` (`uv add aiosmtplib`), sprawdzona w dokumentacji przed
    użyciem, nie z pamięci. Retry (otwarta kwestia w spec, "np. 3"):
    **przyjęte wprost jako 3 próby** z rosnącym odstępem — parametr
    techniczny/operacyjny, nie fakt o użytkowniku, ten sam tryb co
    `BALANCE_TOLERANCE` w kroku 2. **`alert_immediate` — nie subgraph:**
    diagram w `docs/11` rysuje go jako pojedynczy węzeł master grafu, nie
    zagnieżdżony `StateGraph` — zaimplementowany bezpośrednio jako
    `_alert_immediate_node`/`_build_alert_message` (czysta, testowalna
    funkcja bez zależności od SMTP/`Settings`) w `graph/master.py`, bez
    sesji DB (nic nie zapisuje). Treść błędu bierze z nowego pola
    `MasterGraphState.alert_details` (statement_id + failure_reason),
    wypełnianego przez `_verification_pre_check_node`/
    `_verification_post_check_node` przy niepowodzeniu — ta sama zasada co
    już istniejące `verification_ok`/`needs_review` (dane "wyniku tego
    przebiegu", nie nowa kolumna/tabela "już zaalarmowano"). Bez
    `interrupt()`, więc oba węzły **są już podpięte** do `master.py`,
    wyjęte z pętli placeholderów — jedyny wciąż niepodpięty krok to
    `categorization`/`human_review` (czeka na checkpointer, krok 12).
    Testy: `tests/test_email_delivery_graph.py` (sukces, trwały błąd po 3
    próbach bez niezłapanego wyjątku, retry-potem-sukces, zbiera tylko
    `pending`, no-op, temat maila zawiera typ/zakres dat raportu),
    `tests/test_alert_immediate.py` (`_build_alert_message` z jednym i
    wieloma błędami). `tests/test_master_graph.py` zaktualizowany
    (placeholdery dla `EMAIL_DELIVERY`/`ALERT_IMMEDIATE`, `alert_details`
    w stanie startowym).

12. [x] **Master orchestration graph + scheduling** — [`11-spec-orchestration-scheduling`](docs/11-spec-orchestration-scheduling.md):
    złożenie subgraphów 1–11 w master `StateGraph`, checkpointer Postgres,
    schemat `thread_id`. **Najważniejsze: wreszcie podpięty `categorization`**
    (zbudowany w pełni w kroku 6, celowo niepodpięty do teraz — czekał
    dokładnie na to, co ten krok dostarcza). **Nowa zależność, zatwierdzona:**
    `langgraph-checkpoint-postgres` + `psycopg[binary]` (nie goły `psycopg`
    — zweryfikowane bezpośrednio: bez `binary` import failuje brakiem
    systemowego `libpq` na tej maszynie). **Realne odkrycie architektoniczne**
    (zweryfikowane w dokumentacji/źródłach LangGraph, nie zgadywane):
    `CategorizationState` nie ma wspólnych pól z `MasterGraphState`, więc
    nie może być zamontowany przez dosłowne `add_node(nazwa,
    skompilowany_subgraph)` (LangGraph scala tylko nakładające się klucze).
    Rozwiązanie: `_categorization_node` to zwykła funkcja-węzeł (ten sam
    wzorzec co `_fixed_costs_reconciliation_node` i inne), która sama
    otwiera sesję i woła `build_categorization_graph(...).ainvoke(...)` bez
    własnego checkpointera — dziedziczy checkpointer aktywnego przebiegu, a
    `interrupt()` wewnątrz `human_review` i tak poprawnie zatrzymuje **cały**
    master graf (empirycznie potwierdzone syntetycznym testem, nie tylko
    wyczytane z dokumentacji). **Realna konsekwencja:** master-poziomowy
    `HUMAN_REVIEW` (węzeł + `_route_after_categorization` +
    `MasterGraphState.needs_review`) **usunięte** — szkic sprzed
    zbudowania prawdziwego subgraphu; `CAT → FIX` jest teraz bezwarunkowa
    (krok 8 już zdecydował, że `needs_review` wchodzi do bilansu z
    ostrzeżeniem, pipeline nie czeka). `docs/11`'s diagram zaktualizowany.
    Zrobione: `graph/checkpointer.py` (`build_checkpointer`,
    `psycopg_dsn_from_database_url` — psycopg nie zna dialektu
    `+asyncpg`), `scripts/setup_checkpointer.py` (jednorazowe `.setup()`,
    nigdy przy starcie aplikacji), `graph/runner.py`
    (`generate_weekly_thread_id` — ISO tydzień, `run_master_graph` —
    punkt wejścia "logiki wyzwalania", gotowy dla kroku 13/15).
    **Windows-specific, zweryfikowane bezpośrednio:** `psycopg`'s tryb
    async nie działa z domyślnym `ProactorEventLoop` — `WindowsSelectorEventLoopPolicy`
    ustawiona w skrypcie i `tests/conftest.py` (bezpieczne też dla
    `asyncpg`). `build_categorization_graph`'s `checkpointer` param
    rozluźniony do opcjonalnego (był wymagany) — bez zmian w istniejących
    testach. Testy: `tests/test_master_graph_categorization.py` —
    **świadomie syntetyczny** (bez realnej bazy/subgraphu kategoryzacji):
    `_categorization_node` jest sztywno wpięty w `async_session_factory`
    (baza deweloperska, tak jak każdy inny realny węzeł) — nie ma jeszcze
    DI do `TEST_DATABASE_URL`, więc test dowodzi samego **mechanizmu**
    zagnieżdżenia (nested `.ainvoke()` bez `add_node` i tak poprawnie
    propaguje `interrupt()`/`Command(resume=...)`/`get_state_history` do
    grafu zewnętrznego) na minimalnym syntetycznym grafie — logika
    biznesowa kategoryzacji ma już pełne pokrycie w
    `tests/test_categorization_graph.py`. Pełne testy integracyjne z realną
    bazą czekają na DI sesji per-request z kroku 13. `tests/test_checkpointer.py`
    (integracyjny, realny Postgres, pomijany jeśli `TEST_DATABASE_URL`
    nieosiągalny) — DSN transform, `.setup()` faktycznie tworzy tabele.
    `tests/test_master_graph.py` zaktualizowany (usunięty test
    `needs_review`/`human_review`, `categorization_node` teraz też
    wstrzykiwalny placeholder jak każdy inny).

13. [x] **Backend API** — [`13-spec-backend-api`](docs/13-spec-backend-api.md):
    FastAPI opakowujący gotowy master graph, pełna tabela endpointów.
    **Domyka lukę testową z kroku 12** ("pełne testy integracyjne czekają
    na DI sesji per-request z kroku 13") — dokładnie to dostarczone tutaj.
    **Zdecydowane z użytkownikiem:** uwierzytelnienie prostym API key
    (`BACKEND_API_KEY`, nagłówek `X-API-Key`), nie brak-uwierzytelnienia,
    nie basic auth — jedyna otwarta kwestia z docs/13. **Kontrakt 1:1 z
    już istniejącym frontendem** (Plan B krok 1, zbudowany wcześniej na
    mocku): `frontend/src/modules/common/models/api.ts`/`api/client.ts` —
    nie projektowany od nowa, tylko odwzorowany (camelCase JSON przez
    `pydantic.alias_generators.to_camel`). **Realne odkrycie
    architektoniczne:** checkpointer LangGraph nie ma API "wylistuj
    wszystkie thread_id" (sprawdzone w źródłach/forum LangGraph) i nie
    reprezentuje stanu `failed` (nieobsłużony wyjątek nie tworzy
    checkpointa) — stąd nowa, lekka tabela `RUNS` (migracja `f0e0bc389b71`),
    celowo osobna od tabel checkpointera. `StateSnapshot`/`graph.get_graph()`'s
    dokładny kształt (`interrupts: tuple[Interrupt(value, id)]`,
    `Node(id, name, data, metadata)`, `Edge(source, target, data,
    conditional)`) zweryfikowany przez introspekcję zainstalowanego
    `langgraph`, nie z pamięci. Zrobione: `finance_agent/api/{dependencies,
    schemas,routes,app}.py` — 8 endpointów z tabeli w docs/13 + `GET
    /categories` (poza tabelą, ale konsumowany przez frontend). **DI
    dodane do `graph/runner.py`**: `run_master_graph` zyskało
    `session_factory`/`checkpointer_factory`/`graph_factory` (domyślnie
    realne, nadpisywalne w testach) — ten sam DI seam co
    `api/dependencies.py`'s `get_db_session`/`get_checkpointer`/
    `get_run_trigger`, oba rozwiązują dokładnie problem zostawiony
    otwartym w kroku 12. `upsert_run_status` wydzielone jako publiczna,
    reużywalna funkcja (używana i przez `run_master_graph`, i przez `POST
    /runs`). Nowa zależność: `fastapi`/`uvicorn`/`httpx` (już ustalone w
    `CLAUDE.md`/docs/13 jako framework — nie otwarta decyzja jak
    poprzednie biblioteki). Testy: `tests/test_runs_repository.py` (status
    `RUNS` na sukces/błąd/przerwanie/wznowienie, z prawdziwym
    `interrupt()`/`Command(resume=...)` przez `InMemorySaver` i
    placeholderowym master grafem — bez dotykania bazy dev/realnego
    Postgresa/OVH/SMTP), `tests/test_api.py` (`httpx.AsyncClient` +
    `ASGITransport`, `dependency_overrides` na bazę testową — 11
    przypadków: struktura grafu, kategorie, trigger+lista, 404 dla
    nieznanych wątków, resume, health, uwierzytelnienie brak/złe/poprawne
    API key).

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

   **Korekta po realnym podłączeniu do Planu A kroku 13:** wszystkie
   strony pobierające dane (`GraphPage`/`RunsPage`/`RunDetailPage`/
   `ReviewQueuePage`) to Client Components (`'use client'`, fetch w
   `useEffect`) — `client.ts` nie ma własnego `'use client'`, ale skoro
   importują go tylko komponenty kliencie, jego kod i tak leci do bundla
   przeglądarki. Pierwsza wersja wpięcia realnego backendu wysyłała
   `X-API-Key` (`require_api_key`, docs/13) wprost z przeglądarki przez
   `NEXT_PUBLIC_BACKEND_API_KEY` — **błąd**, bo każda zmienna
   `NEXT_PUBLIC_` ląduje w bundlu JS, więc klucz mający gate'ować dostęp
   do backendu był w pełni widoczny w devtoolsach. Naprawione: nowy
   Route Handler `frontend/src/app/api/backend/[...path]/route.ts` jako
   same-origin proxy (wzorzec z oficjalnej dokumentacji Next.js —
   `node_modules/next/dist/docs/01-app/02-guides/backend-for-frontend.md`,
   sekcja „Proxying to a backend") — przegląda żąda `/api/backend/...`
   (ten sam origin, bez CORS), Route Handler działa w procesie Node
   Next.js, tam dopiero dokleja realny `BACKEND_API_KEY` (bez prefiksu,
   serwerowy) do żądania do FastAPI. `client.ts`'s `BASE_URL` uproszczone
   do względnej ścieżki `/api/backend` — cztery strony wymienione wyżej
   **nie zostały w ogóle dotknięte** (świadomie odrzucona alternatywa:
   pełny refaktor na Server Components z fetchowaniem w `page.tsx` —
   wymagałby przepisania też mutacji, `triggerRun`/`resumeRun`/wyboru
   kategorii w Review Queue, i wszystkich ich testów). Testy:
   `route.test.ts` (mock `fetch`, wywołanie `GET`/`POST` bezpośrednio z
   `NextRequest` — forward metody/ścieżki/query, doklejenie
   `X-API-Key`, przekazanie body POST bez zmian, przekazanie statusu/JSON
   błędu 1:1, `502` przy nieosiągalnym backendzie), `client.test.ts`
   zaktualizowany na względne URL-e.

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

5. [x] **Review Queue** — lista transakcji `needs_review` (kontrakt danych z
   [`06-spec-categorization`](docs/06-spec-categorization.md) i
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md)), akcja
   potwierdzenia/korekty wywołująca `POST /runs/{thread_id}/resume`.
   Zrobione: `modules/runs/pages/ReviewQueuePage.tsx`, route
   `/runs/[threadId]/review`, link „Review" na `RunsPage` widoczny tylko
   dla `status === 'waiting_for_review'`. Kontrakt danych wzięty wprost z
   realnego kodu Planu A kroku 6
   (`backend/src/finance_agent/subgraphs/categorization/nodes.py`,
   `make_human_review`/`make_persist_category`): interrupt payload
   `{pending_reviews: [{transaction_id, description, counterparty, amount,
   suggested_category, suggested_confidence}]}`, resume payload
   `{decisions: {transaction_id: category_name}}` — brak decyzji dla danej
   transakcji zostaje `needs_review`, nie błąd. `RunState` w
   `common/models/api.ts` przeprojektowany z płaskiego
   `Record<string, unknown>` na `{values, pendingReviews}`, mirror
   LangGraph `StateSnapshot.values`/`.interrupts` (`values`/`interrupts` to
   osobne pola, nie jeden scalony słownik — sprawdzone bezpośrednio w
   `langgraph.types` w `.venv`); `pendingReviews` dekoduje jedyny dziś
   zdefiniowany kształt interruptu. **Decyzja z użytkownikiem:** dropdown
   kategorii w korekcie zasilany nowym `ApiClient.getCategories()` —
   mock-only rozszerzenie (analogiczne do `nodes`/`edges` w
   `GraphStructureResponse` z kroku 2), celowo **nieobecne** w
   `docs/13-spec-backend-api.md` — czy/jak dodać realny `GET /categories`
   to decyzja backendowa/Python, poza zakresem tej pracy frontendowej.
   `mockClient` rozszerzony o stanowy `reviewState`: `resumeRun` usuwa z
   `pendingReviews` pozycje z decyzją i, gdy lista pustoszeje, przestawia
   status runu na `completed` (mirror realnego zachowania — resume
   odblokowuje graf, który leci dalej do końca). Nowy shadcn komponent
   `select` (`npx shadcn@latest add select`, Base UI `@base-ui/react/select`
   pod spodem — działa w testach Vitest z `@testing-library/user-event`
   bez dodatkowych jsdom shimów, w przeciwieństwie do React Flow w kroku 2).

6. [x] **Manual Trigger** — przycisk „uruchom teraz” wywołujący `POST /runs`.
   Zrobione: `modules/runs/components/TriggerRunButton.tsx` (pierwsze
   użycie shadcn `Button`) na `RunsPage`, obok nagłówka. `mockClient`
   (`common/api/mockClient.ts`) stał się stanowy dla runów (`listRuns`
   czyta z tego, co dopisał `triggerRun`) — wierniej odzwierciedla
   realny backend (`POST` → `GET` pokazuje nowy wpis) niż statyczny
   fixture; `resetMockRuns()` (test-only) trzyma testy deterministycznymi.

7. [x] **Wykresy / breakdowny** — zastosowanie skilla `dataviz` do breakdownów
   kategorii i trendów w Graph View / Run Detail. **Realny stan przy
   starcie tego kroku:** mimo że Plan A krok 8 (Cashflow calculation) jest
   zrobiony, `graph/master.py`'s `_cashflow_calculation_node` odrzuca
   wynik subgraphu (zwraca tylko `{"visited": [...]}`) i `api/routes.py`
   nie ma żadnego endpointu wystawiającego te dane (`reporting` odtwarza
   je tylko wewnętrznie do HTML maila) — większa luka niż przy Review
   Queue (krok 5), gdzie realny kontrakt już istniał. **Decyzja z
   użytkownikiem:** budować na prowizorycznym mocku frontendowym, bez
   ruszania backendu/docs; realny endpoint to osobna decyzja
   backendowa/Python poza zakresem tej pracy. Kontrakt danych mocka wzięty
   1:1 z realnego kodu (`backend/src/finance_agent/subgraphs/cashflow/state.py`:
   `PeriodSummary`/`CategoryBreakdownEntry`/`FixedCostStatusEntry`) — nowe
   typy `CashflowSummary`/`PeriodSummary`/`CategoryBreakdownEntry`/
   `FixedCostStatusEntry` w `common/models/api.ts`, nowa metoda
   `ApiClient.getCashflowSummary(threadId)`; realny `client.ts` rzuca
   czytelny błąd "not implemented" zamiast zgadywać ścieżkę REST (decyzja
   backendowa). Brak jakiejkolwiek wielotygodniowej serii w realnym
   kontrakcie — "trend" to tylko `weekly` (bieżący wyciąg) vs
   `rolling_month` (narastająco), nie historia; mock i UI odzwierciedlają
   to wprost jako dwie równoległe sekcje, bez fabrykowania historii, której
   backend nigdy nie produkuje. **Forma wykresu (skill `dataviz`,
   `choosing-a-form.md`):** breakdown per kategoria to **diverging
   horizontal bar chart**, nie sequential — `category_breakdown` miesza
   przychody (dodatnie) i wydatki (ujemne) w jednej liście, więc pasuje do
   joba "above/below a baseline", nie "compare magnitude". Kolor: token
   Tailwind (`blue-500`/`red-500`), nie surowe hexy z `palette.md` skilla —
   projekt ma już swój system kolorów (`RunStatusBadge`), spójność z nim >
   osobna paleta dla jednego wykresu. Fixed costs status: tabela + badge
   (`FixedCostStatusBadge.tsx`, 1:1 wzorzec `RunStatusBadge.tsx`), nie
   wykres. **Bez nowej biblioteki wykresów** (Recharts/`shadcn add chart`
   itd.) — zgodnie z regułą „tylko oficjalne/ustalone biblioteki, pytaj
   przed dodaniem": wykres w plain SVG/HTML/CSS wg
   `marks-and-anatomy.md`/`components.md` (cienkie słupki `h-6`/24px,
   zaokrąglony data-end przy końcu słupka/kwadratowy przy baseline, jeden
   wspólny baseline/skala `maxAbs`, legenda Income/Expense, hover tooltip
   per słupek, przycisk „Show as table" — accessibility twin wymagany
   przez skill). Zrobione: `modules/runs/components/{StatTile,
   FixedCostStatusBadge,CategoryBreakdownChart,CashflowSummaryPanel}.tsx`;
   `RunDetailPage` woła `getCashflowSummary(threadId)` w osobnym
   `useEffect`/stanie (błąd/loading nigdy nie blokuje istniejącej osi
   czasu/grafu), renderuje panel pod dotychczasowym 3-kolumnowym gridem —
   ten grid dostał stałą wysokość (`h-[480px] shrink-0` zamiast `flex-1`)
   i strona zyskała `overflow-y-auto`, żeby nowa sekcja miała gdzie się
   zmieścić bez łamania istniejącego layoutu wypełniającego viewport.
   Testy: `CategoryBreakdownChart.test.tsx` (słupki+legenda, tooltip na
   hover, przełącznik tabeli), `CashflowSummaryPanel.test.tsx` (obie
   sekcje, stat tile'e, badge per status), `RunDetailPage.test.tsx`
   rozszerzony, `mockClient.test.ts`/`client.test.ts` o `getCashflowSummary`
   (mock zwraca dane; real client rzuca błąd).

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
nie zakładane. (Autoryzacja Drive, biblioteka Graph View, profil
ryzyka/instrumenty/poduszka bezpieczeństwa dla kroku 9 i polityka retry dla
kroku 11 zostały już rozstrzygnięte — patrz odpowiednie specyfikacje — i
nie figurują tu dłużej.)

Obecnie brak otwartych kwestii blokujących kolejne kroki. Jedyny pozostały
"blokujący" element to realne wartości `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/
`SMTP_PASSWORD`/`REPORT_RECIPIENT_EMAIL` w `.env` — ale (patrz krok 11
wyżej) to nie blokuje budowy/testów, tylko realne uruchomienie; użytkownik
uzupełni je sam, nigdy w czacie.
