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
  (rekomendacja inwestycyjna). **Uwaga architektoniczna:** kroki 07/08
  celowo zostawiają swój wynik efemerycznym (brak czytelnika w momencie ich
  implementacji) — `render_weekly` odzyskuje te dane, wywołując
  `build_cashflow_graph(session).ainvoke(...)` bezpośrednio (ten sam
  subgraph co krok 07, użyty jako czarna skrzynka — nie duplikacja logiki,
  tylko ponowne wywołanie; tanie, bo to czysta arytmetyka bez zapisów) i
  odczytując najnowszy `INVESTMENT_RECOMMENDATIONS` z `report_id IS NULL`.
  Alternatywa (przepływ danych przez `MasterGraphState`) odrzucona — byłaby
  niespójna z resztą tego repo, gdzie każdy subgraph sam odtwarza swoje
  wejście z bazy (patrz `fixed_costs`/`cashflow`/`investment`, każdy
  niezależnie odpytujący "bieżący wyciąg").
- **Wyjście:** `REPORTS.content_html` gotowy do wysyłki, `report_type`
  (`weekly` | `monthly`). `persist_report` uzupełnia też
  `INVESTMENT_RECOMMENDATIONS.report_id` (nullable od kroku 09, patrz
  [[08-spec-investment-analysis]]) na wiersz raportu tygodniowego —
  zamyka pętlę otwartą w tamtym kroku. **Znane ograniczenie:** jeśli
  reporting zawiedzie w danym tygodniu, kolejna rekomendacja z
  `investment_analysis` przykryje ją jako "najnowsza niepodłączona" —
  starsze osierocone rekomendacje zostają z `report_id = NULL` na stałe.
  Nie jest to utrata danych, tylko niekompletne powiązanie — poza zakresem
  tego kroku.

## Zawartość raportu

**Format wizualizacji — zdecydowane: same tabele HTML**, bez pasków
CSS/wykresów/obrazków. Najbezpieczniejsze renderowanie między klientami
mailowymi, zero nowych zależności do wizualizacji.

**Raport tygodniowy:**
- Podsumowanie: przychody / wydatki / nadwyżka za tydzień.
- Breakdown wydatków per kategoria (tabela).
- Status kosztów stałych: opłacone / brakujące / ze zmienioną kwotą.
- Lista transakcji oznaczonych jako `needs_review` (jeśli są, oczekujące na
  decyzję człowieka) — sekcja pominięta całkowicie, gdy lista jest pusta.
- Propozycja inwestycyjna za dany tydzień — jawny komunikat "brak
  nadwyżki", gdy `surplus_amount == "0"` lub brak rekomendacji w ogóle.

**Raport miesięczny:**
- To samo co tygodniowy, ale narastająco za miesiąc kalendarzowy (reużywa
  `rolling_month` z [[07-spec-cashflow-calculation]], bez ponownego
  wyliczania).
- Porównanie z poprzednim miesiącem (przychody/wydatki/surplus) — jedyne
  naprawdę nowe zapytanie w tym kroku, ten sam `compute_income_and_expense`
  co [[08-spec-investment-analysis]] już reużywa, na zakresie dat
  poprzedniego miesiąca kalendarzowego.
- Rekomendacja inwestycyjna — reużyta z tygodniowego raportu (jedna
  rekomendacja per przebieg master grafu, nie osobna dla miesiąca).

## Kroki / węzły grafu (subgraph `reporting`)

1. `determine_report_types` — czy bieżące uruchomienie generuje tylko
   raport tygodniowy, czy też miesięczny. „Koniec miesiąca” **zdecydowane
   jako**: `period_end` bieżącego wyciągu mieści się w ostatnich 7 dniach
   swojego miesiąca kalendarzowego (`calendar.monthrange`) — dobór
   implementacyjny (podobnie jak `TREND_LOOKBACK_PERIODS`/
   `ANOMALY_MULTIPLIER` w [[08-spec-investment-analysis]]), bo
   [[11-spec-orchestration-scheduling]] nie precyzuje dokładnego testu,
   tylko "pierwszy przebieg po końcu miesiąca".
2. `render_weekly` / `render_monthly` — wypełnienie szablonu **Jinja2**
   (zdecydowane, dodane jako zależność) danymi z kroków 07/08 (patrz
   „Wejście / Wyjście” wyżej — `render_weekly` odzyskuje efemeryczny wynik
   kroku 07 przez bezpośrednie wywołanie jego subgraphu).
3. `persist_report` — zapis do `REPORTS` ze statusem `pending` (jeszcze nie
   wysłany); uzupełnia `INVESTMENT_RECOMMENDATIONS.report_id` na wiersz
   tygodniowy.

## Zależności

- [[07-spec-cashflow-calculation]], [[08-spec-investment-analysis]] —
  dane źródłowe.
- [[01-spec-data-model]] — `REPORTS`.
- [[10-spec-email-delivery]] — konsumuje `content_html`.
- [[11-spec-orchestration-scheduling]] — decyduje kiedy generować który typ
  raportu.

## Otwarte kwestie

Obie rozstrzygnięte z użytkownikiem przy implementacji (Plan A krok 10):

- ~~Format wizualizacji w mailu HTML...~~ — **zdecydowane: same tabele
  HTML**, patrz „Zawartość raportu” wyżej.
- ~~Język raportu...~~ — polski, potwierdzone przez już istniejącą konwencję
  (każdy string uzasadnienia/rationale napisany w krokach 05–09 jest już po
  polsku).

## Kryteria akceptacji / testy

- Test renderowania: dane wejściowe z fixture'a → HTML zawiera wszystkie
  wymagane sekcje (przychody, wydatki, koszty stałe, rekomendacja).
- Test „brak surplusu” — sekcja inwestycyjna pokazuje odpowiedni komunikat
  zamiast pustej/błędnej sekcji (zarówno gdy nie ma żadnej rekomendacji, jak
  i gdy jest, ale z `surplus_amount == "0"`).
- Test listy `needs_review` — obecna, gdy są transakcje do przeglądu;
  sekcja pominięta całkowicie, gdy lista jest pusta.
- Test „koniec miesiąca” generuje dodatkowo raport miesięczny z poprawnym
  zakresem dat i poprawnym porównaniem z poprzednim miesiącem; wyciąg
  środka miesiąca nie generuje raportu miesięcznego.
- Test `persist_report` faktycznie zapisuje wiersz(e) `REPORTS` i uzupełnia
  `INVESTMENT_RECOMMENDATIONS.report_id`.
- Brak przetworzonego wyciągu → subworkflow kończy się bez błędu, nic nie
  zapisane (no-op, ten sam wzorzec co kroki 05/07/08).
