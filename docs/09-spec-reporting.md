# 09 — Reporting

## Cel

Złożyć wyniki wszystkich poprzednich subworkflowów w czytelny raport —
tygodniowy i miesięczny — gotowy do wysyłki mailem.

## Zakres

Wchodzi: generowanie treści raportu (struktura, sekcje, formatowanie HTML).
Nie wchodzi: sama wysyłka (patrz [[10-spec-email-delivery]]) ani wyliczenia
źródłowe (patrz [[07-spec-cashflow-calculation]], [[08-spec-investment-analysis]]).

## Wejście / Wyjście

- **Wejście:** wynik z [[07-spec-cashflow-calculation]] (bilans, breakdown
  per kategoria, status kosztów stałych) i [[08-spec-investment-analysis]]
  (rekomendacja inwestycyjna).
- **Wyjście:** `REPORTS.content_html` gotowy do wysyłki, `report_type`
  (`weekly` | `monthly`).

## Zawartość raportu

**Raport tygodniowy:**
- Podsumowanie: przychody / wydatki / nadwyżka za tydzień.
- Breakdown wydatków per kategoria (tabela lub prosty wykres — patrz
  `dataviz` przy budowie UI/e-maila HTML).
- Status kosztów stałych: opłacone / brakujące / ze zmienioną kwotą.
- Lista transakcji oznaczonych jako `needs_review` (jeśli są, oczekujące na
  decyzję człowieka).
- Propozycja inwestycyjna za dany tydzień (jeśli surplus > 0).

**Raport miesięczny:**
- To samo co tygodniowy, ale narastająco za miesiąc kalendarzowy.
- Porównanie z poprzednim miesiącem (trend przychodów/wydatków/surplusu).
- Zbiorcza rekomendacja inwestycyjna za miesiąc (nie suma tygodniowych, a
  spójna ocena całego miesiąca — patrz `assess_trend` w
  [[08-spec-investment-analysis]]).

## Kroki / węzły grafu (subgraph `reporting`)

1. `determine_report_types` — czy bieżące uruchomienie generuje tylko
   raport tygodniowy, czy też miesięczny (logika „koniec miesiąca” w
   [[11-spec-orchestration-scheduling]]).
2. `render_weekly` / `render_monthly` — wypełnienie szablonu (Jinja2 lub
   podobny, do potwierdzenia w implementacji) danymi z kroków 07/08.
3. `persist_report` — zapis do `REPORTS` ze statusem `pending` (jeszcze nie
   wysłany).

## Zależności

- [[07-spec-cashflow-calculation]], [[08-spec-investment-analysis]] —
  dane źródłowe.
- [[01-spec-data-model]] — `REPORTS`.
- [[10-spec-email-delivery]] — konsumuje `content_html`.
- [[11-spec-orchestration-scheduling]] — decyduje kiedy generować który typ
  raportu.

## Otwarte kwestie

- Czy raport ma być jeden łączony (prywatne + firmowe w jednym mailu z
  dwiema sekcjami), czy dwa osobne raporty per konto — do ustalenia.
- Format wizualizacji w mailu HTML (proste tabele vs. wbudowane
  wykresy/obrazki) — przy budowie skonsultować skill `dataviz`.
- Język raportu — zakładam polski, zgodnie z językiem komunikacji w tym
  projekcie; do potwierdzenia.

## Kryteria akceptacji / testy

- Test renderowania: dane wejściowe z fixture'a → HTML zawiera wszystkie
  wymagane sekcje (przychody, wydatki, koszty stałe, rekomendacja).
- Test „brak surplusu” — sekcja inwestycyjna pokazuje odpowiedni komunikat
  zamiast pustej/błędnej sekcji.
- Test „koniec miesiąca” generuje dodatkowo raport miesięczny z poprawnym
  zakresem dat.
- Test wizualny (snapshot HTML) na reprezentatywnym zestawie danych.
