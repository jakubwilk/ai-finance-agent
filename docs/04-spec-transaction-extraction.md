# 04 — Transaction Extraction

## Cel

Wyciągnąć z zweryfikowanego wyciągu PDF pełną listę pozycji (linii)
transakcyjnych i znormalizować je do wspólnego formatu, niezależnie od
layoutu konkretnego banku.

## Zakres

Wchodzi: parsowanie tekstu PDF do struktury tabelarycznej, normalizacja pól
(data, kwota, opis, kontrahent, saldo bieżące). Nie wchodzi: przypisanie
kategorii (patrz [[06-spec-categorization]]) ani walidacja sald na poziomie
całego wyciągu (patrz [[03-spec-statement-verification]], choć ten
subworkflow dostarcza dane wejściowe do tamtej walidacji).

## Wejście / Wyjście

- **Wejście:** `STATEMENTS` o statusie `verified` (czyli po pre-check z
  [[03-spec-statement-verification]]), plik PDF.
- **Wyjście:** wiersze w `TRANSACTIONS` (bez `category_id`, wypełniane
  później), `review_status = auto`; `STATEMENTS.opening_balance`/
  `closing_balance` (patrz `derive_statement_balances` niżej).

## Kroki / węzły grafu (subgraph `extraction`)

Rzeczywista implementacja ma 2 węzły — konceptualne kroki `detect_layout` +
`parse_lines` + `normalize` łączą się w jeden `parse_statement` (wybór
parsera i samo parsowanie są nierozdzielne w praktyce), `persist_transactions`
robi zarówno insert jak i `derive_statement_balances` jako efekt uboczny:

1. `parse_statement` — dla każdego wyciągu: pobranie pliku (fetch-on-demand),
   `detect_layout` (który parser z rejestru `matches()` na tekście pierwszej
   strony — pierwszy dopasowany wygrywa, generyczny zawsze pasuje więc jest
   zawsze ostatni), `parse_lines`+`normalize` w jednym wywołaniu
   `parser.parse(text, words_per_page)` zwracającym znormalizowane
   `RawTransaction` (`txn_date`, `amount`, `description`, `counterparty`,
   `running_balance`, `raw_details`).
2. `persist_transactions` — insert do `TRANSACTIONS` powiązanych z
   `statement_id`, oraz `derive_statement_balances`: skoro realny format
   wyciągu (patrz korekta w [[03-spec-statement-verification]]) nie drukuje
   osobno salda początkowego/końcowego, tylko `running_balance` przy każdej
   linii, ten krok wylicza `STATEMENTS.closing_balance` (saldo najnowszej
   sparsowanej transakcji — pierwszej w kolejności, wyciąg jest
   najnowsze-najpierw) i `opening_balance` (saldo najstarszej sparsowanej
   transakcji minus jej własna kwota), zapisuje je na wiersz `STATEMENTS`
   (status zostaje `verified` — na `processed`/`failed` zmienia dopiero
   post-check, `check_balance_consistency`, osobny krok planu).

## Architektura parserów per bank

**Strategy pattern**, teraz z realną implementacją
(`backend/src/finance_agent/subgraphs/extraction/parsers/`): interfejs
`StatementParser` (`matches(first_page_text: str) -> bool`, `parse(text: str,
words_per_page: list[list[Word]]) -> list[RawTransaction]` — parsery
pozycyjne dostają też pozycje słów, parsery na czystym tekście używają
tylko `text`). Rejestr `DEFAULT_PARSERS` w `nodes.py`: pierwszy dopasowany
wygrywa, generyczny zawsze ostatni.

- **`PkoBpHistoriaRachunkuParser`** — dla eksportu „Historia rachunku” PKO
  BP (sprawdzone na realnym przykładzie użytkownika). Kluczowe odkrycie:
  strony z tabelą transakcji **nie mają linii siatki**, więc
  `pdfplumber.extract_tables()` zwraca tam zero tabel (w przeciwieństwie do
  tabeli „Zastosowane kryteria wyboru” z pre-checku). Parsowanie idzie przez
  `extract_words()` (pozycje x0/top) — potwierdzone empirycznie stabilne
  granice kolumn: Data operacji (~0-85), Data waluty (~85-133), Typ
  transakcji (~133-200), Opis (~200-450), Kwota (~450-512), Saldo (~512+).
  `layout_utils.cluster_words_into_rows` (bankowo-agnostyczne, reużywalne)
  grupuje słowa w wiersze po `top`; nowa transakcja zaczyna się tylko gdy
  kolumna „Data operacji” pasuje do `\d{4}-\d{2}-\d{2}` (bez tego,
  powtarzający się nagłówek strony fałszywie dopasowywałby się jako
  transakcja). `Opis` parsowany generycznie jako pary `etykieta : wartość`
  (bez twardego kodowania per typ transakcji — w jednym tygodniu wystąpiło
  12+ różnych `Typ transakcji`: Kapitalizacja odsetek, Prowizja, Przelew na
  rachunek, Płatność kartą, Polecenie zapłaty, Zlecenie stałe, Przelew BLIK
  - zwrot, Wypłata z bankomatu, Przelew z rachunku, Przelew na rachunek
  własny — stała lista pól per typ byłaby krucha i niekompletna).
  `description` = wartość `Tytuł`; `counterparty` = `Odbiorca` jeśli jest,
  inaczej `Nadawca`, inaczej `None` (płatności kartą nie mają żadnego).
  Wszystko poza tym (`Lokalizacja`, `Adres`, `Miasto`, `Kraj`, `Numer
  karty`, `Nr rachunku`, `Referencje`, `Identyfikator`, `Data wykonania
  operacji`, `Oryginalna kwota operacji`, `Typ transakcji`) trafia do
  `TRANSACTIONS.raw_details` (jsonb) — nic nie jest odrzucane, ale nic z
  tego nie ma własnej kolumny (decyzja użytkownika).
- **`GenericLineParser`** — zawsze `matches() → True` (ostatni fallback),
  regex na linię tekstu `data + opis + kwota`, bez `counterparty`/
  `running_balance`/`raw_details` — celowo niskiej wierności, zgodnie z
  pierwotnym założeniem tej sekcji.

`txn_date` = **Data operacji** (data księgowania — zdecydowane z
użytkownikiem, zgadza się z kolejnością wierszy i z tym, kiedy pieniądze
faktycznie znikają/pojawiają się na koncie), nie Data waluty.

## Biblioteka do parsowania PDF

`pdfplumber` (MIT, aktywnie utrzymywany), już dodany przy implementacji
[[03-spec-statement-verification]] — potwierdzone, że wystarcza też tutaj,
choć inaczej niż w pre-checku: `extract_tables()` nie działa na stronach z
transakcjami (brak linii siatki), więc `PkoBpHistoriaRachunkuParser` używa
`extract_words()` zamiast `extract_tables()`.

## Zależności

- [[03-spec-statement-verification]] — dostarcza plik po pre-check,
  konsumuje wynik do post-check sald.
- [[01-spec-data-model]] — `TRANSACTIONS`.
- [[06-spec-categorization]] — konsumuje wyekstrahowane, nieskategoryzowane
  transakcje.

## Otwarte kwestie

- Lista banków w praktyce używanych (konto prywatne) — na razie tylko PKO
  BP (eksport „Historia rachunku”) potwierdzony na realnym przykładzie;
  kolejne parsery dodawane iteracyjnie, gdy pojawi się kolejny bank/format.

## Kryteria akceptacji / testy

Zamiast fixture'ów PDF per bank (co oznaczałoby commitowanie realnych
danych finansowych do publicznego repo, albo dorabianie osobnej
zależności tylko do generowania testowych PDF-ów) — testy budują ręcznie
słowniki pozycji słów (`{"text", "x0", "top"}`) naśladujące dokładnie ten
kształt, jaki faktycznie zwraca `pdfplumber.extract_words()` na realnym
przykładzie (potwierdzone empirycznie), z fikcyjnymi wartościami:

- Test płatności kartą (bez `counterparty`, `raw_details` z
  Lokalizacja/Adres/Miasto/Kraj/Numer karty).
- Test przelewu wychodzącego (`counterparty` z `Odbiorca`) i przychodzącego
  (`counterparty` z `Nadawca`).
- Test opłaty/prowizji bez kontrahenta.
- Test zawiniętego (wielolinijkowego) `Typ transakcji` i wartości `Tytuł`.
- Test odporności na powtarzający się nagłówek strony (nie tworzy
  fałszywej transakcji).
- Test `GenericLineParser` na prostych liniach tekstu.
- Test integracyjny na `db_session` (fake drive client + fake extractor):
  insert `TRANSACTIONS`, poprawne wyliczenie `opening_balance`/
  `closing_balance` na `STATEMENTS`, status zostaje `verified`.
