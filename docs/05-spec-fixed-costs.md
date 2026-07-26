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

- **Wejście:** tabela `FIXED_COSTS` (dane dostarczy użytkownik — patrz
  „Otwarte kwestie”), nowo skategoryzowane `TRANSACTIONS` z bieżącego
  okresu.
- **Wyjście:** powiązanie transakcji z odpowiadającym kosztem stałym (pole
  pomocnicze, np. `TRANSACTIONS.matched_fixed_cost_id` — do dodania do
  modelu danych przy implementacji, patrz uwaga w [[01-spec-data-model]]),
  lista rozbieżności do uwzględnienia w raporcie.

## Kroki / węzły grafu (subgraph `fixed_costs_reconciliation`)

1. `load_active_fixed_costs` — pobranie aktywnych (`active = true`) kosztów
   stałych dla danego konta/okresu.
2. `match_transactions` — dla każdego aktywnego kosztu stałego, szukanie w
   transakcjach bieżącego okresu pozycji o zbliżonej kwocie
   (`expected_amount` ± tolerancja) i/lub dopasowanym kontrahencie/opisie.
3. `flag_discrepancies` — dla kosztów bez dopasowania w oczekiwanym oknie
   czasowym (`due_day` ± tolerancja dni) → flaga „brak płatności”; dla
   dopasowanych transakcji z inną kwotą niż `expected_amount` → flaga
   „zmiana kwoty”.
4. `persist_reconciliation` — zapis wyników do wykorzystania przez
   [[07-spec-cashflow-calculation]] i [[09-spec-reporting]].

## Zależności

- [[01-spec-data-model]] — `FIXED_COSTS`.
- [[06-spec-categorization]] — dopasowanie działa najlepiej po
  kategoryzacji (koszt stały ma przypisaną kategorię).
- [[07-spec-cashflow-calculation]] — konsumuje wynik dopasowania.

## Otwarte kwestie

- **Realna zawartość tabeli kosztów stałych** — użytkownik dostarczy ją
  później (nazwa, kwota, częstotliwość, dzień płatności); do tego czasu
  tabela jest pusta, subworkflow nie ma nic do dopasowania (no-op, nie
  błąd).
- Tolerancja kwoty i okna czasowego dopasowania (np. ± 5% kwoty, ± 3 dni) —
  do ustalenia z użytkownikiem lub jako konfigurowalny parametr.
- Czy koszty stałe mogą się różnić między kontem prywatnym a firmowym w tej
  samej tabeli, czy to dwie oddzielne listy — zakładam, że `FIXED_COSTS`
  jest powiązane z `account_id` (do dodania do modelu, patrz
  [[01-spec-data-model]]).

## Kryteria akceptacji / testy

- Fixture z jednym kosztem stałym i pasującą transakcją → dopasowanie
  poprawne.
- Fixture z kosztem stałym bez odpowiadającej transakcji w oknie → flaga
  „brak płatności”.
- Fixture z transakcją o innej kwocie niż oczekiwana → flaga „zmiana
  kwoty”.
- Test no-op na pustej tabeli `FIXED_COSTS` (subworkflow kończy się bez
  błędu).
