# 07 — Cashflow Calculation

## Cel

Wyliczyć bilans przychodów i wydatków za dany okres (tydzień, miesiąc
narastająco), uwzględniając koszty stałe, i wyznaczyć nadwyżkę (surplus)
dostępną do analizy inwestycyjnej.

## Zakres

Wchodzi: agregacja skategoryzowanych transakcji, breakdown per kategoria,
uwzględnienie statusu kosztów stałych, wyliczenie surplusu. Nie wchodzi:
sama propozycja inwestycyjna (patrz [[08-spec-investment-analysis]]) ani
formatowanie raportu (patrz [[09-spec-reporting]]).

## Wejście / Wyjście

- **Wejście:** `TRANSACTIONS` skategoryzowane (`review_status IN (auto,
  confirmed, needs_review)` — patrz „Otwarte kwestie” niżej) dla bieżącego
  wyciągu, wynik dopasowania kosztów stałych z [[05-spec-fixed-costs]]
  (`TRANSACTIONS.matched_fixed_cost_id`, już trwały w bazie).
- **Wyjście:** struktura wyliczeń (przychody total, wydatki total per
  kategoria, koszty stałe: opłacone/brakujące/zmiana kwoty, `surplus =
  przychody - wydatki`, zarówno dla bieżącego wyciągu jak i narastająco dla
  miesiąca), przekazywana dalej do [[08-spec-investment-analysis]] i
  [[09-spec-reporting]]. **Zdecydowane: wyliczenie efemeryczne**, zwracane
  przez subgraph i trzymane tylko w stanie grafu między węzłami w obrębie
  jednego przebiegu master grafu — ten sam wzorzec co reconciliation w
  [[05-spec-fixed-costs]] (brak osobnej tabeli, bo kroki 08/09 jeszcze nie
  istnieją i nie ma czytelnika, który wymagałby trwałości).

## Kroki / węzły grafu (subgraph `cashflow_calculation`)

1. `aggregate_income_expense` — suma `amount > 0` (przychody) i `amount <
   0` (wydatki) dla okresu, per konto.
2. `breakdown_by_category` — grupowanie wydatków/przychodów po
   `category_id`.
3. `apply_fixed_costs_status` — dołączenie informacji z reconciliation
   (opłacone / brakujące / zmiana kwoty) z [[05-spec-fixed-costs]].
4. `compute_surplus` — `surplus = total_income - total_expense`
   (uwzględniając już rozliczone koszty stałe, nie osobno).
5. `compute_rolling_month` — to samo zestawienie narastająco dla bieżącego
   miesiąca kalendarzowego (potrzebne dla raportu miesięcznego, patrz
   [[09-spec-reporting]] i [[11-spec-orchestration-scheduling]]).

## Zależności

- [[06-spec-categorization]] — wymaga skategoryzowanych transakcji.
- [[05-spec-fixed-costs]] — status dopasowania kosztów stałych.
- [[08-spec-investment-analysis]] — konsumuje `surplus`.
- [[09-spec-reporting]] — konsumuje pełne zestawienie.

## Otwarte kwestie

Obie kwestie rozstrzygnięte z użytkownikiem przy implementacji (Plan A krok 8):

- ~~Czy transakcje ze statusem `needs_review`...~~ — **zdecydowane: wliczone,
  z ostrzeżeniem.** Liczą się do sum wg tymczasowej kategorii z LLM
  (`category_source="llm"`) — pieniądze faktycznie wyszły z konta niezależnie
  od statusu przeglądu. `needs_review_count` w wyniku pozwala raportowi
  (docs/09) ostrzec, ile transakcji czeka na potwierdzenie, zamiast po cichu
  prezentować niepotwierdzoną kategoryzację jako pewną.
- ~~Definicja „tygodnia”...~~ — **zdecydowane: okres bieżącego wyciągu**
  (`STATEMENTS.period_start`/`period_end`), nie ISO tydzień kalendarzowy.
  „Bieżący wyciąg” = ten sam koncept co w [[05-spec-fixed-costs]] (najpóźniejszy
  `period_end` wśród `status == "processed"`) — spójne z resztą pipeline'u,
  bez osobnej logiki kalendarzowej.

## Kryteria akceptacji / testy

- Test na fixture'ach z znanym zestawem transakcji → oczekiwane sumy
  przychodów/wydatków/surplus zgadzają się z ręcznym wyliczeniem.
- Test breakdown per kategoria sumuje się do total wydatków (brak
  „zgubionych” transakcji bez kategorii w sumie końcowej — powinny być
  widoczne jako `Nieskategoryzowane`, nie zniknąć).
- Test narastającego miesiąca: dodanie kolejnego tygodnia poprawnie
  aktualizuje sumę miesięczną.
