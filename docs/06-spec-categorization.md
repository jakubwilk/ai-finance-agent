# 06 — Categorization

## Cel

Przypisać każdej wyekstrahowanej transakcji odpowiednią kategorię z tabeli
`CATEGORIES`, łącząc szybkie reguły deterministyczne z klasyfikacją LLM dla
przypadków niejednoznacznych, oraz kierować transakcje o niskiej pewności do
przeglądu przez człowieka.

## Zakres

Wchodzi: dopasowanie regułowe, fallback LLM, próg pewności, kolejka do
przeglądu (human-in-the-loop). Nie wchodzi: definicja samych kategorii
(realne dane dostarczy użytkownik przez `data/local/categories.json`,
gitignored — patrz
[[01-spec-data-model#przechowywanie-realnej-zawartości-categories-i-fixed_costs]])
ani wyliczenia bilansu (patrz [[07-spec-cashflow-calculation]]).

## Wejście / Wyjście

- **Wejście:** `TRANSACTIONS` z `category_id IS NULL` (świeżo
  wyekstrahowane), tabela `CATEGORIES`.
- **Wyjście:** `TRANSACTIONS.category_id`, `category_source` (`rule` |
  `llm` | `manual`), `category_confidence`, `review_status`.

## Kroki / węzły grafu (subgraph `categorization`)

**Zaimplementowane** (`backend/src/finance_agent/subgraphs/categorization/`):

1. `rule_match` — dopasowanie po słowniku kontrahent/opis → kategoria,
   tabela `CATEGORY_RULES` ([[01-spec-data-model]]). Klucz dopasowania
   (`match_key`) to `counterparty` gdy transakcja go ma, inaczej
   `description` (lowercased/stripped). Trafienie = `category_source =
   rule`, `category_confidence = 1.0`, `review_status = auto`.
2. `llm_classify` — dla transakcji bez trafienia regułowego: wywołanie
   modelu przez `llm/client.py` (`build_classification_model`, patrz
   [[12-spec-llm-integration-ollama]]) ze strukturalnym promptem (lista
   dostępnych kategorii + opis/kontrahent/kwota transakcji),
   `ChatOpenAI.with_structured_output(ClassificationResult,
   method="function_calling")` → `category + confidence`. **Nie
   zweryfikowane na żywym endpoincie OVH** — `method="function_calling"`
   wybrany jako najszerzej wspierany w heterogenicznych backendach
   OpenAI-compatible (gpt-oss/Qwen/Mistral), do potwierdzenia przy
   pierwszym realnym uruchomieniu. Każdy wyjątek (sieć, parsowanie,
   nieznana nazwa kategorii zwrócona przez model) → `category_confidence =
   0.0`, nie przerywa całego batcha (patrz [[12-spec-llm-integration-ollama]]
   „fallback”).
3. `confidence_gate` — `category_confidence >= 0.85` → `review_status =
   auto`; poniżej → `review_status = needs_review`. **Zdecydowane: próg
   0.85** (bardziej konserwatywnie niż pierwotnie proponowane 0.7 — mniej
   automatycznych błędów kategoryzacji kosztem więcej ręcznego przeglądu).
4. `human_review` (tylko gdy jest co najmniej jedna `needs_review`) —
   **jeden** `interrupt()` na cały bieżący batch (nie per transakcja):
   `{"pending_reviews": [...]}`, wznowienie `Command(resume={"decisions":
   {transaction_id: category_name}})`. Batch zamiast jednej transakcji na
   raz, żeby Review Queue w UI ([[14-spec-frontend-ui]]) mogła zebrać
   wszystkie decyzje i wysłać jedno żądanie wznowienia, nie N. Brak
   decyzji dla danej transakcji w odpowiedzi → zostaje `needs_review`,
   nieskategoryzowana (nie błąd). Potwierdzone/skorygowane = `category_source
   = manual`, `review_status = confirmed`.
5. `persist_category` — zapis do `TRANSACTIONS`; dla `category_source =
   manual` dodatkowo upsert `CATEGORY_RULES` (**zdecydowane: automatyczne
   uczenie się** — potwierdzenie/korekta człowieka zawsze nadpisuje starą
   regułę). Zapis reguły celowo *po* `interrupt()`, nie przed — zgodnie z
   `langgraph-human-in-the-loop`: kod przed `interrupt()` wykonuje się
   ponownie przy każdym wznowieniu, więc efekty uboczne muszą być po nim.

**Ważne: krok nie jest jeszcze podpięty do `master.py`.** `interrupt()`
wymaga checkpointera, a wznowienie może przyjść osobnym żądaniem dni
później (`POST /runs/{thread_id}/resume`, Plan B krok 5) — to wymaga
checkpointera/schematu `thread_id` na poziomie master grafu, czyli kroku 12
(jeszcze nie zbudowanego). Subgraph jest w pełni zaimplementowany i
przetestowany (`build_categorization_graph`, własny checkpointer
przekazywany przez wywołującego — `InMemorySaver` w testach), ale
wywoływany bezpośrednio, nie przez placeholder `CATEGORIZATION` w master
grafie.

## Zależności

- [[04-spec-transaction-extraction]] — dostarcza transakcje do
  skategoryzowania.
- [[01-spec-data-model]] — `CATEGORIES`, `TRANSACTIONS`.
- [[12-spec-llm-integration-ollama]] — model do klasyfikacji.
- [[14-spec-frontend-ui]] — interfejs do `human_review`.
- [[07-spec-cashflow-calculation]] — konsumuje skategoryzowane transakcje.

## Otwarte kwestie

- Do czasu, aż użytkownik uzupełni `data/local/categories.json` (patrz
  [[01-spec-data-model]]), ten subworkflow nie ma z czym pracować
  end-to-end na realnych danych (nie blokuje samej implementacji logiki —
  pokryte testami na fixture'ach).
- Podpięcie do `master.py` — zablokowane przez brak master-poziomowego
  checkpointera/`thread_id` (krok 12), patrz sekcja „Kroki” wyżej.
- `method="function_calling"` dla structured output — niezweryfikowany na
  żywym endpoincie OVH AI Endpoints, do potwierdzenia przy pierwszym
  realnym uruchomieniu (patrz sekcja „Kroki”).

## Kryteria akceptacji / testy

`test_categorization_graph.py` (`db_session` + `InMemorySaver` + fake chat
model — bez realnego wywołania OVH API):

- Test regułowy: znany `match_key` → poprawna kategoria, LLM nigdy
  wywołany (asercja na fake modelu, który rzuca wyjątkiem jeśli go użyto).
- Test LLM powyżej progu: `category_source = llm`, `review_status = auto`,
  brak `interrupt()`.
- Test LLM poniżej progu: graf wstrzymuje się (`__interrupt__` w wyniku),
  `Command(resume={"decisions": {...}})` poprawnie wznawia, zapisuje
  `category_source = manual`/`review_status = confirmed`, i **tworzy nową
  regułę w `CATEGORY_RULES`** (uczenie się).
- Test błędu LLM (wyjątek): traktowany jak pewność 0.0 → `needs_review`,
  nie przerywa batcha.
- Test bez transakcji do kategoryzacji: kończy się bez wywołania
  `interrupt()`.
