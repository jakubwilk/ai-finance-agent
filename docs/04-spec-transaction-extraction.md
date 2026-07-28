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

- **Wejście:** `STATEMENTS` po pre-check z [[03-spec-statement-verification]],
  plik PDF.
- **Wyjście:** wiersze w `TRANSACTIONS` (bez `category_id`, wypełniane
  później), `review_status = auto`.

## Kroki / węzły grafu (subgraph `extraction`)

1. `detect_layout` — rozpoznanie, z jakiego banku pochodzi wyciąg (np. po
   charakterystycznym nagłówku/logo w tekście), żeby wybrać właściwy
   parser. Dopóki nie ma dopasowania → parser generyczny (heurystyka
   „data + kwota + opis w jednej linii”) jako fallback.
2. `parse_lines` — parser specyficzny dla layoutu (lub generyczny) zamienia
   surowy tekst PDF na listę wierszy z polami: `txn_date`, `amount`,
   `description`, `counterparty` (jeśli wyodrębnialny), `running_balance`.
3. `normalize` — ujednolicenie formatu daty, separatora dziesiętnego,
   znaku kwoty (wpływ dodatni / wydatek ujemny), przycięcie białych znaków
   w opisach.
4. `persist_transactions` — insert do `TRANSACTIONS` powiązanych z
   `statement_id`.

## Architektura parserów per bank

Ponieważ layout różni się między bankami, a nie znamy jeszcze wszystkich
banków, które będą używane — projekt zakłada **strategy pattern**: interfejs
`StatementParser` (metody `matches(text) -> bool`, `parse(text) ->
list[RawTransaction]`), z rejestrem implementacji dodawanych iteracyjnie w
miarę pojawiania się nowych banków w praktyce. Parser generyczny jest
zawsze fallbackiem ostatnim w kolejności.

## Biblioteka do parsowania PDF (do ustalenia w implementacji)

Nie zakładam konkretnej biblioteki na tym etapie — zgodnie z zasadą „check
documentation before guessing” z `CLAUDE.md`, wybór (np. `pdfplumber` vs.
`pypdf` vs. `pymupdf`) zostanie zweryfikowany względem aktualnej
dokumentacji i wsparcia dla ekstrakcji tabel przy pisaniu kodu, nie na
etapie spec.

## Zależności

- [[03-spec-statement-verification]] — dostarcza plik po pre-check,
  konsumuje wynik do post-check sald.
- [[01-spec-data-model]] — `TRANSACTIONS`.
- [[06-spec-categorization]] — konsumuje wyekstrahowane, nieskategoryzowane
  transakcje.

## Otwarte kwestie

- Konkretna biblioteka PDF do parsowania tekstu/tabel — ustalić przy
  implementacji po sprawdzeniu dokumentacji.
- Lista banków w praktyce używanych (konto prywatne) — nieznana teraz;
  parsery dodawane iteracyjnie na podstawie realnych przykładów wyciągów.
- Czy `counterparty` da się wiarygodnie wyodrębnić z opisu transakcji dla
  każdego banku, czy zostanie połączony z `description` gdy nie da się
  rozdzielić.

## Kryteria akceptacji / testy

- Zestaw fixture'ów PDF (co najmniej jeden przykładowy wyciąg per bank
  faktycznie używany) z oczekiwaną listą transakcji jako „złoty” wynik do
  porównania (snapshot testing).
- Test `detect_layout` poprawnie wybiera dedykowany parser, a nie
  generyczny fallback, dla znanych banków.
- Test normalizacji: różne formaty dat/kwot w wejściu dają identyczny
  format wyjściowy.
- Test na wyciągu z nietypowymi znakami (np. polskie znaki diakrytyczne w
  opisach) — brak utraty/uszkodzenia danych.
