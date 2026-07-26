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
  confirmed)`) dla danego `account_id` i okresu, wynik dopasowania kosztów
  stałych z [[05-spec-fixed-costs]].
- **Wyjście:** struktura wyliczeń (przychody total, wydatki total per
  kategoria, koszty stałe: opłacone/brakujące, `surplus = przychody -
  wydatki`), przekazywana dalej do [[08-spec-investment-analysis]] i
  [[09-spec-reporting]]. Do ustalenia przy implementacji, czy to trwały
  rekord w bazie, czy wyliczenie efemeryczne trzymane tylko w stanie grafu
  (`state`) między węzłami.

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

- Czy transakcje ze statusem `needs_review` (jeszcze niepotwierdzone przez
  człowieka) mają być wliczone do bilansu z ostrzeżeniem, czy pominięte do
  czasu potwierdzenia — wpływa na dokładność raportu wysłanego w terminie,
  jeśli przegląd człowieka się opóźni.
- Definicja „tygodnia” do agregacji (tydzień kalendarzowy ISO vs. okres od
  ostatniego wyciągu) — prawdopodobnie zgodna z cyklem wgrywania wyciągów,
  do potwierdzenia.

## Kryteria akceptacji / testy

- Test na fixture'ach z znanym zestawem transakcji → oczekiwane sumy
  przychodów/wydatków/surplus zgadzają się z ręcznym wyliczeniem.
- Test breakdown per kategoria sumuje się do total wydatków (brak
  „zgubionych” transakcji bez kategorii w sumie końcowej — powinny być
  widoczne jako `Nieskategoryzowane`, nie zniknąć).
- Test narastającego miesiąca: dodanie kolejnego tygodnia poprawnie
  aktualizuje sumę miesięczną.
