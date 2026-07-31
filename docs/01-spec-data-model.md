# 01 — Data Model

## Cel

Zdefiniować schemat bazy danych współdzielony przez wszystkie subworkflowy:
przechowuje wyciągi, transakcje, kategorie, koszty stałe, raporty i
rekomendacje inwestycyjne, oraz stan checkpointera LangGraph.

## Zakres

Wchodzi: schemat tabel domenowych i ich relacje. Nie wchodzi: konkretna
zawartość danych referencyjnych (konta, kategorie, koszty stałe, ustawienia
inwestycyjne) — dostarczy je użytkownik później; to jest tylko struktura,
którą wypełnią. Zobacz niżej („Przechowywanie realnej zawartości”) gdzie i
jak ta rzeczywista zawartość będzie przechowywana — repo jest publiczne,
więc to nie może być zwykły commitowany plik.

## Wybór silnika bazy danych

**Ostateczny wybór: PostgreSQL.** Używany identycznie we wszystkich
środowiskach — lokalnie (development) oraz po deployu (dev/prod) — bez
SQLite jako alternatywy, żeby uniknąć rozjazdu zachowania między
środowiskami. Powody: współdzielony dostęp backend + graf + checkpointer
LangGraph w jednej instancji, łatwy deploy jako serwis w Coolify, brak
problemów z równoczesnym zapisem jakie miewa SQLite pod obciążeniem
wieloprocesowym (patrz `langgraph-persistence` dla konfiguracji
checkpointera Postgres).

## Model danych

```mermaid
erDiagram
    ACCOUNTS ||--o{ STATEMENTS : "posiada"
    STATEMENTS ||--o{ TRANSACTIONS : "zawiera"
    CATEGORIES ||--o{ TRANSACTIONS : "kategoryzuje"
    CATEGORIES ||--o{ FIXED_COSTS : "kategoryzuje"
    CATEGORIES ||--o{ CATEGORY_RULES : "przypisana przez regułę"
    FIXED_COSTS ||--o{ TRANSACTIONS : "dopasowuje (opcjonalnie)"
    REPORTS |o--o{ INVESTMENT_RECOMMENDATIONS : "zawiera (opcjonalnie, patrz uwaga niżej)"

    ACCOUNTS {
        uuid id PK
        text display_name
        text bank_name
        timestamptz last_synced_at "kursor synchronizacji ingestion, NULL do pierwszego przebiegu"
        timestamptz created_at
    }

    STATEMENTS {
        uuid id PK
        uuid account_id FK
        text drive_file_id "unikalny identyfikator pliku z Drive"
        text file_name
        text checksum "sha256 pobranego pliku"
        date period_start "nullable do czasu verification pre-check"
        date period_end "nullable do czasu verification pre-check"
        numeric opening_balance "nullable do czasu ekstrakcji (krok 04)"
        numeric closing_balance "nullable do czasu ekstrakcji (krok 04)"
        text status "pending | verified | failed | processed"
        text failure_reason
        timestamptz ingested_at
        timestamptz verified_at
    }

    TRANSACTIONS {
        uuid id PK
        uuid statement_id FK
        uuid category_id FK "nullable do czasu kategoryzacji"
        date txn_date
        numeric amount "dodatnia = wpływ, ujemna = wydatek"
        text description
        text counterparty
        numeric running_balance
        text category_source "rule | llm | manual"
        numeric category_confidence
        text review_status "auto | needs_review | confirmed"
        jsonb raw_details "pola z Opis/Typ transakcji poza description/counterparty, patrz [[04-spec-transaction-extraction]]"
        uuid matched_fixed_cost_id FK "nullable, ustawiane przez fixed_costs_reconciliation, patrz [[05-spec-fixed-costs]]"
    }

    CATEGORIES {
        uuid id PK
        text name
        int score "0-100, im wyższe tym bardziej niezbędne do życia"
        text type "income | expense | transfer"
    }

    FIXED_COSTS {
        uuid id PK
        uuid category_id FK
        text name
        numeric expected_amount
        text frequency "monthly | quarterly | yearly"
    }

    CATEGORY_RULES {
        uuid id PK
        text match_key "unikalny: counterparty jeśli jest, inaczej description, lowercased/stripped"
        uuid category_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    REPORTS {
        uuid id PK
        text report_type "weekly | monthly"
        date period_start
        date period_end
        text content_html
        text delivery_status "pending | sent | failed"
        timestamptz generated_at
        timestamptz sent_at
    }

    INVESTMENT_SETTINGS {
        uuid id PK
        text risk_profile "conservative | balanced | aggressive"
        numeric safety_buffer_amount
        jsonb instruments "np. [\"etf\", \"term_deposit\", \"savings_account\"]"
    }

    INVESTMENT_RECOMMENDATIONS {
        uuid id PK
        uuid report_id FK "nullable, patrz uwaga niżej"
        numeric surplus_amount
        text rationale
        jsonb allocation_proposal
        timestamptz created_at
    }
```

## Uwagi projektowe

- `ACCOUNTS` trzyma dokładnie jeden wiersz — agent śledzi wyłącznie jedno,
  prywatne konto (zdecydowane z użytkownikiem; przelewy z konta firmowego
  trafiają na prywatne jako zwykły wpływ, więc firmowe nie jest częścią tego
  systemu). Stąd brak kolumny "typu" konta i brak `account_id` na `REPORTS`
  (jest tylko jedno konto, więc nic nie trzeba rozróżniać).
- `TRANSACTIONS.category_id` jest nullable — pipeline musi działać nawet
  zanim kategoryzacja się zakończy (patrz [[06-spec-categorization]]).
- `CATEGORY_RULES.match_key` samo się uczy: `persist_category`
  (kategoryzacja) upsertuje wiersz za każdym razem, gdy `human_review`
  potwierdzi/skoryguje kategorię — kolejna transakcja z tym samym
  kontrahentem/opisem trafi regułowo, bez ponownego wywołania LLM ani
  przeglądu. Klucz to `counterparty`, jeśli transakcja go ma (stabilniejszy
  dla przelewów niż zmienny `Tytuł`), inaczej `description` (jedyny sygnał
  przy płatnościach kartą).
- `CATEGORIES.score` jest zarezerwowany pod przyszłą analizę (np. podział
  wydatków na niezbędne/nieniezbędne) — żaden subgraph go jeszcze nie
  konsumuje, to nie jest jeszcze twarde wymaganie funkcjonalne.
- `STATEMENTS.checksum` + `drive_file_id` razem zapobiegają podwójnemu
  przetworzeniu tego samego wyciągu (patrz [[03-spec-statement-verification]]).
- `TRANSACTIONS.matched_fixed_cost_id` jest jedyną trwałą daną z
  reconciliation kosztów stałych — sama lista rozbieżności (brak
  płatności/zmiana kwoty) jest efemeryczna, zwracana przez subgraph i
  konsumowana od razu w tym samym przebiegu master grafu, nie ma osobnej
  tabeli (patrz [[05-spec-fixed-costs]]).
- `INVESTMENT_RECOMMENDATIONS.allocation_proposal` jako `jsonb` — kształt
  `{instrument: kwota_pln}`, klucze ograniczone do instrumentów
  potwierdzonych w [[08-spec-investment-analysis]] (`etf`/`term_deposit`/
  `savings_account`).
- `INVESTMENT_RECOMMENDATIONS.report_id` jest nullable — `investment_analysis`
  biegnie przed `reporting` w master grafie
  ([[11-spec-orchestration-scheduling]]), więc żaden `Report` jeszcze nie
  istnieje w momencie zapisu rekomendacji. Krok 10 (reporting) uzupełnia
  `report_id` po utworzeniu wiersza `Report` — ten sam "nullable aż do
  momentu, gdy kolejny krok zna wartość" wzorzec co `Statement.period_start`/
  `period_end`/`opening_balance`/`closing_balance` (patrz [[08-spec-investment-analysis]]).
- Checkpointer LangGraph (tabele `checkpoints`, `checkpoint_writes` itd.)
  będzie żył w tej samej instancji Postgres, ale to osobne tabele zarządzane
  przez bibliotekę `langgraph-checkpoint-postgres`, nie modelowane tutaj
  ręcznie — patrz [[11-spec-orchestration-scheduling]].

## Zależności

Używane przez niemal wszystkie pozostałe specyfikacje (02–11).

## Przechowywanie realnej zawartości `ACCOUNTS`, `CATEGORIES`, `FIXED_COSTS` i `INVESTMENT_SETTINGS`

**Zdecydowane** (repo jest publiczne na GitHubie, więc te dane — nazwy
banków/kont, kategorii, kwoty kosztów stałych, kontrahenci, poduszka
bezpieczeństwa, profil ryzyka — nie mogą trafić do gita jako zwykłe pliki):

- Realne wartości żyją wyłącznie w plikach `data/local/accounts.json`,
  `data/local/categories.json`, `data/local/fixed_costs.json` i
  `data/local/investment_settings.json`, objętych `.gitignore` (nigdy nie
  trafiają do repozytorium).
- Struktura JSON odzwierciedla pola z ER diagramu wyżej: `ACCOUNTS` →
  tablica z co najwyżej jednym elementem (`display_name`, `bank_name` —
  jedno śledzone konto, patrz „Uwagi projektowe” wyżej); `CATEGORIES` →
  `name`, `score` (0-100, wymagane), `type`; `FIXED_COSTS` →
  `name`, `category` (odwołanie po nazwie kategorii, nie po `uuid`),
  `expected_amount`, `frequency`; `INVESTMENT_SETTINGS` → tablica z co
  najwyżej jednym elementem (`risk_profile`, `safety_buffer_amount`,
  `instruments` — patrz [[08-spec-investment-analysis]]).
- W repo commitowane są tylko szablony `data/local/accounts.example.json`,
  `data/local/categories.example.json`, `data/local/fixed_costs.example.json`
  i `data/local/investment_settings.example.json` z fikcyjnymi wartościami —
  pokazują kształt danych, nie realną zawartość.
- Skrypt seedujący (`backend/scripts/seed_reference_data.py`) wczytuje te
  pliki JSON i zapisuje je do Postgresa idempotentnie (konto/ustawienia
  inwestycyjne: dopasowanie do jedynego istniejącego wiersza, błąd jeśli
  źródło ma więcej niż jeden wpis; kategorie/koszty stałe: dopasowanie po
  `name`; `FIXED_COSTS.category` mapowane na `category_id` po nazwie
  kategorii) — bezpieczny do wielokrotnego uruchamiania.
- Sekrety (API keys, hasła) to osobna kategoria, patrz reguła 6 w
  `CLAUDE.md` — ta sekcja dotyczy danych osobistych/finansowych, nie
  credentiali.

## Kryteria akceptacji / testy

- Migracje tworzą wszystkie tabele bez błędów na czystej instancji Postgres.
- Testy integralności: nie da się wstawić `TRANSACTIONS` bez istniejącego
  `STATEMENTS`; unikalność `(account_id, drive_file_id)` w `STATEMENTS`
  uniemożliwia duplikat.
- Test migracji w obie strony (up/down) na pustej bazie testowej.
