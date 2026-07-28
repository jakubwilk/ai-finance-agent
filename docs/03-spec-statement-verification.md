# 03 — Statement Verification

## Cel

Zweryfikować, że pobrany wyciąg (`STATEMENTS`, status `pending`) jest
kompletny i wewnętrznie spójny, zanim jego linie zostaną wyciągnięte i
policzone. To bezpośrednia realizacja wymogu z briefu: „zweryfikować czy są
pobrane (czy nie mają błędów w kwotach)”.

## Zakres

Wchodzi: sprawdzenie czytelności pliku, spójność sald, wykrycie duplikatów.
Nie wchodzi: parsowanie pełnej listy transakcji (to robi
[[04-spec-transaction-extraction]]).

**Korekta na podstawie realnego przykładu:** ten punkt pierwotnie zakładał,
że pre-check może tanio odczytać saldo początkowe/końcowe z nagłówka/stopki
wyciągu. Realny eksport z PKO BP („Historia rachunku") — sprawdzony na
przykładowym pliku dostarczonym przez użytkownika — **nie ma** takiego pola
nigdzie. Ma za to tabelę „Zastosowane kryteria wyboru" z jawnym `Od dnia`/
`Do dnia` (to nadal tanie, niezależne od pełnego parsowania linii) oraz
kolumnę „Saldo po transakcji" przy **każdej** transakcji — z czego
`opening_balance`/`closing_balance` da się wyliczyć dopiero po
sparsowaniu pierwszego i ostatniego wiersza tabeli transakcji, czyli
faktycznie w [[04-spec-transaction-extraction]], nie tutaj. Stąd realny
zakres pre-checku to: czytelność PDF, odczyt `period_start`/`period_end`
z tabeli kryteriów, sprawdzenie duplikatów — bez sald.

## Wejście / Wyjście

- **Wejście:** `STATEMENTS` ze statusem `pending` + plik PDF.
- **Wyjście:** aktualizacja `STATEMENTS.status` → `verified` lub `failed`
  (+ `failure_reason`); przy `failed` — zdarzenie do `ALERT` (patrz niżej).

## Kroki / węzły grafu (subgraph `verification`)

**Pre-check** (przed ekstrakcją, tanie — implementacja w kodzie łączy dwa
konceptualne kroki w jeden węzeł `read_statement`, bo oba potrzebują tego
samego parsowania pdfplumber tych samych pobranych bajtów):

1. `read_statement` — pobranie pliku (fetch-on-demand, jak w ingestion),
   próba odczytu tekstu z PDF (jeśli brak warstwy tekstowej — skan/zdjęcie
   → `failed` z powodem `unreadable_pdf`, fallback OCR patrz „Otwarte
   kwestie”), odczyt `period_start`/`period_end` z tabeli „Zastosowane
   kryteria wyboru” (`Od dnia`/`Do dnia`) — jeśli ta tabela nie istnieje
   albo dat nie da się sparsować → `failed` z powodem
   `unparseable_period` (nowy, jawny powód błędu zamiast cichego
   ignorowania, zgodnie z regułą 1 z `CLAUDE.md`).
2. `check_duplicate` — czy inny wyciąg o statusie `verified`/`processed`
   ma zakres dat pokrywający się z (`period_start`–`period_end`) tego
   wyciągu → jeśli tak, `failed` z powodem `duplicate_statement`.
   (Duplikat po `(account_id, drive_file_id)` jest już niemożliwy do
   zaobserwowania tutaj — unikalność tej pary jest wymuszona na stałe
   przez constraint w [[01-spec-data-model]], więc drugi wiersz z tym
   samym plikiem nigdy się nie wstawi.)
3. `mark_result` — zapis `status`/`failure_reason` per wyciąg.

**Post-check** (po ekstrakcji — patrz [[04-spec-transaction-extraction]]):

4. `check_balance_consistency` — `opening_balance`/`closing_balance` są
   wyliczane przez ekstrakcję (z pierwszego/ostatniego sparsowanego wiersza
   tabeli transakcji, patrz korekta wyżej), więc ten krok jest teraz
   sprawdzeniem spójności własnego parsowania, nie porównaniem z
   niezależnie wydrukowaną liczbą: `opening_balance + Σ(transactions.amount)
   == closing_balance` (z tolerancją zaokrągleń, np. 0.01).
5. `mark_result` (post-check) — aktualizacja `status` → `verified`/
   `processed` albo `failed` z powodem `balance_mismatch`.

## Obsługa błędu

Gdy `status = failed`: pipeline **nie** przechodzi dalej do kategoryzacji
dla tego wyciągu. Zamiast tego trafia do węzła `ALERT`, który (do ustalenia
w [[10-spec-email-delivery]]) wysyła powiadomienie o błędzie od razu, a nie
czeka na cykl tygodniowy — błąd w kwotach ma być wykryty szybko, nie
dopiero w raporcie tygodniowym.

## Zależności

- [[02-spec-google-drive-ingestion]] — dostarcza plik do weryfikacji.
- [[04-spec-transaction-extraction]] — dostarcza linie do post-check sald.
- [[01-spec-data-model]] — `STATEMENTS.status`, `failure_reason`.

## Otwarte kwestie

- Czy w praktyce wystąpią skany/zdjęcia wyciągów (wymagające OCR), czy
  zawsze będzie to natywny PDF tekstowy eksportowany z bankowości
  elektronicznej — wpływa na to, czy OCR (np. `pytesseract`) w ogóle trzeba
  budować, czy to zbędna złożoność na start.
- Tolerancja zaokrągleń przy porównaniu sald (grosze) — do ustalenia,
  proponowana wartość domyślna 0.01 PLN.
- Kanał natychmiastowego alertu o błędzie (mail od razu vs. inny kanał) —
  patrz [[10-spec-email-delivery]].

## Kryteria akceptacji / testy

- Fixture z poprawnym wyciągiem → `status = verified`.
- Fixture ze sztucznie popsutym saldem końcowym → `status = failed`,
  `failure_reason = balance_mismatch`.
- Fixture z zakresem dat pokrywającym się z już `verified` wyciągiem →
  `failure_reason = duplicate_statement`.
- Fixture z nieczytelnym PDF (pusty tekst) → `failure_reason =
  unreadable_pdf`.
- Fixture bez tabeli „Zastosowane kryteria wyboru” / niesparsowalnych dat →
  `failure_reason = unparseable_period`.
