# 05 — Fixed Costs

## Cel

Modelować i wykorzystywać tabelę kosztów stałych (wydatków, które się nie
zmieniają, np. czynsz, abonamenty, raty) do dwóch celów: (1) automatycznego
dopasowania transakcji do oczekiwanych kosztów, (2) wykrywania rozbieżności
(brak spodziewanej płatności, zmiana kwoty bez zapowiedzi).

## Zakres

Wchodzi: struktura `FIXED_COSTS`, logika dopasowania do `TRANSACTIONS`,
wykrywanie rozbieżności. Nie wchodzi: samo wyliczenie bilansu — to konsumuje
[[07-spec-cashflow-calculation]].

## Wejście / Wyjście

- **Wejście:** tabela `FIXED_COSTS` (realne dane dostarczy użytkownik przez
  `data/local/fixed_costs.json`, gitignored — patrz
  [[01-spec-data-model#przechowywanie-realnej-zawartości-categories-i-fixed_costs]]),
  nowo skategoryzowane `TRANSACTIONS` z bieżącego okresu.
- **Wyjście:** powiązanie transakcji z odpowiadającym kosztem stałym (pole
  pomocnicze, np. `TRANSACTIONS.matched_fixed_cost_id` — do dodania do
  modelu danych przy implementacji, patrz uwaga w [[01-spec-data-model]]),
  lista rozbieżności do uwzględnienia w raporcie.

## Kroki / węzły grafu (subgraph `fixed_costs_reconciliation`)

1. `load_fixed_costs` — pobranie kosztów stałych dla danego konta/okresu
   (tabela nie ma flagi aktywności — każdy wpis jest brany pod uwagę;
   użytkownik usuwa/edytuje wpis bezpośrednio w JSON, gdy koszt przestaje
   obowiązywać).
2. `match_transactions` — dla każdego kosztu stałego, szukanie w
   transakcjach bieżącego okresu pozycji o zbliżonej kwocie
   (`expected_amount` ± tolerancja) i/lub dopasowanym kontrahencie/opisie.
3. `flag_discrepancies` — dla kosztów bez dopasowania w obrębie okresu
   bieżącego wyciągu (`STATEMENTS.period_start`/`period_end`) → flaga „brak
   płatności”; dla dopasowanych transakcji z inną kwotą niż
   `expected_amount` → flaga „zmiana kwoty”.
4. `persist_reconciliation` — zapis wyników do wykorzystania przez
   [[07-spec-cashflow-calculation]] i [[09-spec-reporting]].

## Zależności

- [[01-spec-data-model]] — `FIXED_COSTS`.
- [[06-spec-categorization]] — dopasowanie działa najlepiej po
  kategoryzacji (koszt stały ma przypisaną kategorię).
- [[07-spec-cashflow-calculation]] — konsumuje wynik dopasowania.

## Otwarte kwestie

- Do czasu, aż użytkownik uzupełni `data/local/fixed_costs.json` (patrz
  [[01-spec-data-model]]) i backend zaimplementuje seed do Postgresa, tabela
  jest pusta — subworkflow nie ma nic do dopasowania (no-op, nie błąd).
- Tolerancja kwoty dopasowania (np. ± 5%) — do ustalenia z użytkownikiem lub
  jako konfigurowalny parametr.

## Kryteria akceptacji / testy

- Fixture z jednym kosztem stałym i pasującą transakcją → dopasowanie
  poprawne.
- Fixture z kosztem stałym bez odpowiadającej transakcji w okresie
  bieżącego wyciągu → flaga „brak płatności”.
- Fixture z transakcją o innej kwocie niż oczekiwana → flaga „zmiana
  kwoty”.
- Test no-op na pustej tabeli `FIXED_COSTS` (subworkflow kończy się bez
  błędu).
