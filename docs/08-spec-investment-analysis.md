# 08 — Investment Analysis

## Cel

Przeanalizować nadwyżkę finansową (surplus) wyliczoną w
[[07-spec-cashflow-calculation]] i zaproponować użytkownikowi, jak część
tych środków mogłaby zostać zainwestowana.

## Zakres

Wchodzi: logika analizy surplusu i generowania propozycji alokacji. Nie
wchodzi: wykonywanie jakichkolwiek operacji finansowych — agent **wyłącznie
sugeruje**, nigdy nie składa zleceń ani nie przenosi środków.

## Wejście / Wyjście

- **Wejście:** `surplus` bieżącego wyciągu (dopasowanego do tego samego
  konceptu „bieżącego wyciągu" co [[05-spec-fixed-costs]]/
  [[07-spec-cashflow-calculation]] — najpóźniejszy `period_end` wśród
  `status == "processed"`; przeliczany tu na nowo, nie odczytywany z kroku
  07, który jest efemeryczny), historia surplusów z poprzednich okresów
  (do oceny trendu), `InvestmentSettings` (profil ryzyka, poduszka
  bezpieczeństwa, dostępne instrumenty — patrz niżej).
- **Wyjście:** `INVESTMENT_RECOMMENDATIONS` (kwota, uzasadnienie,
  `allocation_proposal` jako `{instrument: kwota_pln}`), konsumowane przez
  [[09-spec-reporting]]. **Uwaga schematu:** `report_id` jest `NULL` w
  momencie zapisu — `investment_analysis` biegnie przed `reporting` w
  master grafie (`CAT → FIX → CALC → INV → REP → MAIL`,
  [[11-spec-orchestration-scheduling]]), więc żaden `Report` jeszcze nie
  istnieje. Krok 10 (reporting, jeszcze niezaimplementowany) jest
  odpowiedzialny za uzupełnienie `report_id` po utworzeniu wiersza
  `Report` — ten sam wzorzec co stopniowo uzupełniane pola `Statement`
  (docs/01).

## Kroki / węzły grafu (subgraph `investment_analysis`)

1. `check_safety_buffer` — nadwyżka bieżącego okresu minus poduszka
   bezpieczeństwa (`InvestmentSettings.safety_buffer_amount`) odjęta od
   bieżącego salda konta (`Statement.closing_balance`); jeśli surplus ≤ 0
   → kwota do inwestycji zerowa. W przeciwnym razie:
   `investable_amount = min(surplus, max(closing_balance -
   safety_buffer_amount, 0))` — jeśli to mniej niż cały surplus, poduszka
   „wiąże" (`buffer_binding`), z wyjaśnieniem w raporcie.
2. `assess_trend` — porównanie bieżącego surplusu ze średnią z do 3
   poprzednich wyciągów `processed` (`TREND_LOOKBACK_PERIODS = 4` łącznie z
   bieżącym — implementacyjny dobór, docs nie precyzowały liczby). Mniej niż
   2 wyciągi w historii → `insufficient_history` (brak korekty, jak
   "pusta tabela → no-op" w krokach 05/07). W przeciwnym razie: bieżący
   surplus > 2× średnia poprzednich (`ANOMALY_MULTIPLIER = 2`) → anomalia;
   kwota do propozycji zostaje wtedy ograniczona do tej średniej (ostrożniej
   niż pełny, potencjalnie jednorazowy surplus).
3. `generate_allocation_proposal` — jeśli kwota do inwestycji to 0, LLM
   pomijany całkowicie (deterministyczne uzasadnienie: „Brak nadwyżki do
   zainwestowania" / „Nadwyżka poniżej poduszki bezpieczeństwa"). W
   przeciwnym razie: `chat_model.with_structured_output(AllocationResult,
   method="function_calling")` (ten sam wzorzec co
   [[06-spec-categorization]]'s `llm_classify`) ze stałym schematem
   (`etf_percent`/`term_deposit_percent`/`savings_account_percent`/
   `rationale` — stałe pola, nie dynamiczny słownik, bezpieczniejsze dla
   function-calling), prompt zawiera profil ryzyka i listę dostępnych
   instrumentów. Błąd LLM lub procenty niesumujące się do ~100 → **równy
   podział** między dostępne instrumenty jako bezpieczny fallback (ten sam
   „nigdy nie wywalaj batcha" wzorzec co `llm_classify`).
4. `persist_recommendation` — zapis do `INVESTMENT_RECOMMENDATIONS` z
   `report_id = NULL` (patrz „Wejście / Wyjście" wyżej).

## Otwarte kwestie (rozstrzygnięte z użytkownikiem, Plan A krok 9)

- **Profil ryzyka użytkownika** — **zdecydowane: zbalansowany.** Przekazywany
  do LLM w `generate_allocation_proposal` jako kontekst promptu; nie
  hardkodowany jako sztywne wagi procentowe w kodzie (patrz "Kroki / węzły
  grafu" niżej).
- **Dostępne instrumenty inwestycyjne** — **zdecydowane: ETF-y, lokaty
  (`term_deposit`), konto oszczędnościowe (`savings_account`)**. Nie: obligacje
  skarbowe, IKE/IKZE. Klucze angielskie, zgodnie z konwencją istniejących
  enumów (`Category.type`, `FixedCost.frequency`).
- **Wielkość poduszki bezpieczeństwa** — **zdecydowane: stała kwota PLN**
  (nie "N miesięcy wydatków"). To realne dane osobiste — żyje wyłącznie w
  gitignorowanym `data/local/investment_settings.json` (ten sam wzorzec co
  `ACCOUNTS`/`CATEGORIES`/`FIXED_COSTS`, patrz
  [[01-spec-data-model#przechowywanie-realnej-zawartości]]), nigdy w kodzie
  ani w tym dokumencie.
- **Zakres automatyzacji** — **zdecydowane jako jawna decyzja bezpieczeństwa,
  nie tylko domyślne założenie: agent wyłącznie sugeruje.** Zero integracji
  z jakimkolwiek API maklerskim/bankowym do wykonania operacji, teraz i w
  przyszłości.

## Zależności

- [[07-spec-cashflow-calculation]] — dostarcza `surplus`.
- [[12-spec-llm-integration-ollama]] — reasoning tekstowy.
- [[09-spec-reporting]] — konsumuje rekomendację do treści raportu.
- [[01-spec-data-model]] — `INVESTMENT_RECOMMENDATIONS`.

## Kryteria akceptacji / testy

- Test `check_safety_buffer`: surplus mniejszy niż próg bezpieczeństwa →
  rekomendacja zerowa lub zredukowana, z jawnym uzasadnieniem w treści;
  surplus ≤ 0 → kwota zerowa bez wywołania LLM.
- Test `assess_trend`: pojedynczy nietypowo wysoki surplus (odstający od
  historii) → `is_anomaly`, kwota propozycji ograniczona do średniej
  historycznej; mniej niż 2 wyciągi w historii → `insufficient_history`.
- Test `generate_allocation_proposal`: prawidłowy podział z LLM → kwoty per
  instrument zgodne z procentami; błąd LLM/nieprawidłowa suma procentów →
  równy podział fallback, batch się nie wywala.
- Test end-to-end na fixture'ach z historycznymi surplusami → deterministyczna
  część logiki (safety buffer, trend) daje powtarzalny wynik niezależnie od
  LLM; brak `InvestmentSettings` → no-op, nic nie zapisane.
