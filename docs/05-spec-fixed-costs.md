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
2. `match_transactions` — dla każdego kosztu stałego, szukanie wśród
   transakcji bieżącego wyciągu (te ze statusem `processed` o najpóźniejszym
   `period_end`) kandydata z tym samym `category_id` co koszt stały
   (kategoryzacja działa zawsze przed tym krokiem — **zdecydowane**, sygnał
   dopasowania to `category_id`, nie fuzzy-matching po
   kontrahencie/opisie); przy kilku kandydatach w tej samej kategorii wygrywa
   ten o kwocie najbliższej `expected_amount` (żeby dwa koszty stałe w jednej
   kategorii nie „walczyły” o tę samą transakcję).
3. `flag_discrepancies` — dla kosztów bez znalezionego kandydata → flaga
   „brak płatności” (`missing_payment`); dla dopasowanego kandydata w
   granicach tolerancji kwoty → `matched`; poza tolerancją → „zmiana kwoty”
   (`amount_changed`) — **ważne:** tolerancja decyduje o klasyfikacji
   rozbieżności, nie o tym, czy dopasowanie w ogóle istnieje (inaczej
   transakcja o mocno zmienionej kwocie nigdy nie zostałaby powiązana ze
   swoim kosztem stałym i błędnie wyglądałaby jak `missing_payment`).
4. `persist_reconciliation` — zapisuje wyłącznie
   `TRANSACTIONS.matched_fixed_cost_id` dla dopasowanych transakcji
   (`matched`/`amount_changed`). Lista rozbieżności sama w sobie nie ma
   osobnej tabeli — jest efemeryczna, zwracana przez subgraph i konsumowana
   w tym samym przebiegu master grafu przez [[07-spec-cashflow-calculation]]
   i [[09-spec-reporting]] (obie jeszcze niezaimplementowane).

## Zależności

- [[01-spec-data-model]] — `FIXED_COSTS`.
- [[06-spec-categorization]] — dopasowanie działa najlepiej po
  kategoryzacji (koszt stały ma przypisaną kategorię).
- [[07-spec-cashflow-calculation]] — konsumuje wynik dopasowania.

## Otwarte kwestie

Obie poniższe kwestie zostały rozstrzygnięte z użytkownikiem przy
implementacji (Plan A krok 7):

- ~~Do czasu, aż użytkownik uzupełni `data/local/fixed_costs.json`...~~ —
  seed już zaimplementowany (Plan A krok 0); subworkflow jest jednak nadal
  no-op (nie błąd) gdy tabela `FIXED_COSTS` jest pusta lub gdy nie ma
  żadnego wyciągu o statusie `processed`.
- ~~Tolerancja kwoty dopasowania...~~ — **zdecydowane: 5% `expected_amount`**,
  stała w kodzie (`AMOUNT_TOLERANCE_RATIO` w
  `subgraphs/fixed_costs/nodes.py`), nie parametr konfiguracyjny — ten sam
  wzorzec co `BALANCE_TOLERANCE`/`DEFAULT_THRESHOLD` w innych subgrafach.

## Kryteria akceptacji / testy

- Fixture z jednym kosztem stałym i pasującą transakcją → dopasowanie
  poprawne.
- Fixture z kosztem stałym bez odpowiadającej transakcji w okresie
  bieżącego wyciągu → flaga „brak płatności”.
- Fixture z transakcją o innej kwocie niż oczekiwana → flaga „zmiana
  kwoty”.
- Test no-op na pustej tabeli `FIXED_COSTS` (subworkflow kończy się bez
  błędu).
