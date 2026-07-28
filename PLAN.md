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

0. [ ] **Fundament** — scaffold repo (skille `langgraph-python-quickstart`,
   `langchain-dependencies`), lokalny PostgreSQL, migracje wg
   [`01-spec-data-model`](docs/01-spec-data-model.md), skrypt seedujący
   `data/local/*.json` → tabele `CATEGORIES`/`FIXED_COSTS` (patrz sekcja
   „Przechowywanie realnej zawartości” w tej specyfikacji).
   *Blokujące: brak — start od razu.*

1. [ ] **Ingestion** — [`02-spec-google-drive-ingestion`](docs/02-spec-google-drive-ingestion.md):
   monitoring folderów Drive, pobieranie plików, zapis do `STATEMENTS`.
   Autoryzacja: OAuth kontem osobistym użytkownika, zmienne
   `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`/`GOOGLE_OAUTH_REFRESH_TOKEN`
   — **zdecydowane**, blokujące nie ma.

2. [ ] **Verification — pre-check** — [`03-spec-statement-verification`](docs/03-spec-statement-verification.md)
   (kroki 1–3): czytelność PDF, odczyt sald z nagłówka/stopki, sprawdzenie
   duplikatów.

3. [ ] **Extraction** — [`04-spec-transaction-extraction`](docs/04-spec-transaction-extraction.md):
   wzorzec `StatementParser` (strategy pattern) + parser generyczny jako
   fallback. Wybór biblioteki PDF zweryfikowany względem aktualnej
   dokumentacji przy implementacji, nie z pamięci.

4. [ ] **Verification — post-check** — [`03-spec-statement-verification`](docs/03-spec-statement-verification.md)
   (krok 4): pełna zgodność sald po ekstrakcji.

5. [ ] **LLM integration — fundament** — [`12-spec-llm-integration-ollama`](docs/12-spec-llm-integration-ollama.md):
   klient `ChatOllama`, timeout/retry/fallback, przed kategoryzacją bo ta
   go konsumuje. Format zmiennych ustalony (`OLLAMA_BASE_URL`,
   `OLLAMA_MODEL_*`, `OLLAMA_API_KEY`).
   *Blokujące: konkretne wartości (URL, nazwy modeli) — do uzupełnienia
   przez użytkownika w `.env` przed uruchomieniem, nie do zgadnięcia.*

6. [ ] **Categorization** — [`06-spec-categorization`](docs/06-spec-categorization.md):
   `rule_match` → `llm_classify` → `confidence_gate` → `interrupt()` do
   przeglądu człowieka → zapis. Pierwszy kamień milowy wymagający
   `langgraph-human-in-the-loop`.

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

0. [ ] **Scaffold** — skill `init-frontend` (Next.js, TypeScript, Tailwind,
   Vitest), następnie shadcn/ui dokładnie wg ustalenia w `CLAUDE.md`:
   `npx shadcn@latest init` → `npx shadcn@latest apply --preset
   byZfcT1E0` → `npx shadcn@latest add <component>` w miarę potrzeb
   kolejnych widoków.

1. [ ] **Klient API + warstwa mocków** — typowany klient zgodny 1:1 z tabelą
   endpointów w [`13-spec-backend-api`](docs/13-spec-backend-api.md),
   oparty na lokalnym mock/fixture serwerze, żeby praca nad UI nie czekała
   na Plan A krok 13. Po jego ukończeniu — przełączenie na realny base URL
   backendu.

2. [ ] **Graph View** — renderowanie struktury grafu przy użyciu **React
   Flow** (`@xyflow/react` — zdecydowane, patrz
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md)); wymaga osobnej
   biblioteki auto-layoutu (np. `dagre`/`elkjs`); podświetlenie aktualnie
   wykonywanego węzła dla trwających runów.

3. [ ] **Runs / History** — lista `GET /runs` z odznakami statusu.

4. [ ] **Run Detail (time travel)** — `GET /runs/{thread_id}/history` jako oś
   czasu kroków z podglądem stanu na dowolnym checkpointcie.

5. [ ] **Review Queue** — lista transakcji `needs_review` (kontrakt danych z
   [`06-spec-categorization`](docs/06-spec-categorization.md) i
   [`14-spec-frontend-ui`](docs/14-spec-frontend-ui.md)), akcja
   potwierdzenia/korekty wywołująca `POST /runs/{thread_id}/resume`.
   *Zależy od Planu A kroku 6 (Categorization) — realny kształt danych.*

6. [ ] **Manual Trigger** — przycisk „uruchom teraz” wywołujący `POST /runs`.

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
| Konkretne wartości `OLLAMA_BASE_URL`/`OLLAMA_MODEL_*` (format zmiennych już ustalony) | Plan A krok 5 | [`12-spec-llm-integration-ollama`](docs/12-spec-llm-integration-ollama.md) |
| Profil ryzyka, lista instrumentów inwestycyjnych, wielkość poduszki bezpieczeństwa | Plan A krok 9 | [`08-spec-investment-analysis`](docs/08-spec-investment-analysis.md) |
| Konkretne wartości SMTP i adresów odbiorców (format zmiennych już ustalony) | Plan A krok 11 | [`10-spec-email-delivery`](docs/10-spec-email-delivery.md) |
