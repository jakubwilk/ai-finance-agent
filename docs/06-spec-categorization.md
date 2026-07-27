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

1. `rule_match` — dopasowanie po słowniku kontrahent/opis → kategoria
   (utrzymywanym oddzielnie, uzupełnianym z czasem na podstawie
   potwierdzeń z kroku 4). Trafienie regułowe = `category_source = rule`,
   `category_confidence = 1.0`, `review_status = auto`.
2. `llm_classify` — dla transakcji bez trafienia regułowego: wywołanie
   modelu Ollama (patrz [[12-spec-llm-integration-ollama]]) ze
   strukturalnym promptem (lista dostępnych kategorii + opis transakcji),
   odpowiedź jako `category + confidence` (structured output, patrz
   `langchain-middleware`).
3. `confidence_gate` — warunkowa krawędź: `category_confidence >= próg` →
   `review_status = auto`; poniżej progu → `review_status = needs_review`.
4. `human_review` (tylko dla `needs_review`) — `interrupt()` zgodnie z
   `langgraph-human-in-the-loop`; człowiek potwierdza/koryguje kategorię
   przez UI (patrz [[14-spec-frontend-ui]]), wynik zapisany jako
   `category_source = manual`, `review_status = confirmed`. Potwierdzone
   dopasowania mogą zasilać słownik reguł z kroku 1 (uczenie się w czasie).
5. `persist_category` — zapis finalnej kategorii do `TRANSACTIONS`.

## Zależności

- [[04-spec-transaction-extraction]] — dostarcza transakcje do
  skategoryzowania.
- [[01-spec-data-model]] — `CATEGORIES`, `TRANSACTIONS`.
- [[12-spec-llm-integration-ollama]] — model do klasyfikacji.
- [[14-spec-frontend-ui]] — interfejs do `human_review`.
- [[07-spec-cashflow-calculation]] — konsumuje skategoryzowane transakcje.

## Otwarte kwestie

- Do czasu, aż użytkownik uzupełni `data/local/categories.json` (patrz
  [[01-spec-data-model]]), ten subworkflow nie ma z czym pracować (blokujące
  dla end-to-end testu, ale nie dla samej implementacji logiki).
- Próg pewności do `needs_review` (np. 0.7?) — do ustalenia, prawdopodobnie
  empirycznie po pierwszych uruchomieniach.
- Czy słownik reguł ma się automatycznie uczyć z potwierdzeń człowieka, czy
  to osobna, ręcznie kuratorowana lista — założenie robocze: automatyczne
  uczenie, do potwierdzenia.

## Kryteria akceptacji / testy

- Test regułowy: znany kontrahent → poprawna kategoria bez wywołania LLM.
- Test LLM fallback: nieznany kontrahent → wywołanie modelu, parsowanie
  structured output, poprawne pola `category`/`confidence`.
- Test `confidence_gate`: wartości powyżej/poniżej progu trafiają na
  właściwą ścieżkę.
- Test `human_review`: `interrupt()` wstrzymuje graf, `Command(resume=...)`
  z decyzją człowieka poprawnie wznawia i zapisuje wynik.
