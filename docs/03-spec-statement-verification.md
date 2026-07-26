# 03 — Statement Verification

## Cel

Zweryfikować, że pobrany wyciąg (`STATEMENTS`, status `pending`) jest
kompletny i wewnętrznie spójny, zanim jego linie zostaną wyciągnięte i
policzone. To bezpośrednia realizacja wymogu z briefu: „zweryfikować czy są
pobrane (czy nie mają błędów w kwotach)”.

## Zakres

Wchodzi: sprawdzenie czytelności pliku, spójność sald, wykrycie duplikatów.
Nie wchodzi: parsowanie pełnej listy transakcji (to robi
[[04-spec-transaction-extraction]] — weryfikacja może jednak potrzebować
wstępnego, lekkiego odczytania sald z nagłówka/stopki wyciągu, niezależnie
od pełnego parsowania linii).

## Wejście / Wyjście

- **Wejście:** `STATEMENTS` ze statusem `pending` + plik PDF.
- **Wyjście:** aktualizacja `STATEMENTS.status` → `verified` lub `failed`
  (+ `failure_reason`); przy `failed` — zdarzenie do `ALERT` (patrz niżej).

## Kroki / węzły grafu (subgraph `verification`)

1. `check_readability` — próba odczytu tekstu z PDF. Jeśli brak warstwy
   tekstowej (skan/zdjęcie) → fallback OCR (patrz „Otwarte kwestie”) lub
   `failed` z powodem `unreadable_pdf`.
2. `extract_header_footer_balances` — lekkie parsowanie samego nagłówka
   (saldo początkowe) i stopki (saldo końcowe) wyciągu, bez pełnej
   ekstrakcji linii.
3. `check_duplicate` — czy `(account_id, drive_file_id)` lub zakres dat
   (`period_start`–`period_end`) już istnieje w bazie jako `verified`/
   `processed` → jeśli tak, `failed` z powodem `duplicate_statement`.
4. `check_balance_consistency` — po pełnej ekstrakcji linii (krok
   wykonywany faktycznie po [[04-spec-transaction-extraction]], ale
   logicznie należący do weryfikacji — patrz uwaga niżej):
   `opening_balance + Σ(transactions.amount) == closing_balance`
   (z tolerancją zaokrągleń, np. 0.01).
5. `mark_result` — zapis statusu + `failure_reason` jeśli dotyczy.

**Uwaga o kolejności:** pełna suma transakcji wymaga, żeby ekstrakcja
(krok 04) już się wykonała. W praktyce `verification` jest split na dwie
fazy: **pre-check** (kroki 1–3, przed ekstrakcją, tanie i szybkie) i
**post-check** (krok 4, po ekstrakcji, właściwa walidacja sald). Diagram w
[[00-spec-overview-architecture]] upraszcza to do jednego węzła — przy
implementacji grafu rozbić na `verify_pre` → `extract` → `verify_post`.

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
- Fixture z powtórzonym plikiem → `failure_reason = duplicate_statement`.
- Fixture z nieczytelnym PDF (pusty tekst) → `failure_reason =
  unreadable_pdf`.
