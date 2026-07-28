# 02 — Google Drive Ingestion

## Cel

Wykryć i pobrać nowe wyciągi bankowe wgrywane przez użytkownika na Dysk
Google, zanim jakikolwiek dalszy krok (weryfikacja, ekstrakcja) się zacznie.

## Zakres

Wchodzi: monitorowanie folderów Drive, pobieranie nowych plików PDF, zapis
metadanych w `STATEMENTS`. Nie wchodzi: parsowanie zawartości pliku (patrz
[[04-spec-transaction-extraction]]) ani walidacja poprawności (patrz
[[03-spec-statement-verification]]).

## Struktura Drive

Jeden folder z wyciągami konta prywatnego — nazwa/ścieżka dowolna, nie jest
niczym ustalona odgórnie; system zna go wyłącznie po ID skonfigurowanym w
`.env`. Każdy nowy wyciąg trafia jako pojedynczy plik PDF do tego folderu.
Nazewnictwo plików nie jest ujednolicone z góry — subworkflow nie polega na
parsowaniu nazwy pliku, tylko na treści (patrz
[[04-spec-transaction-extraction]]).

## Wejście / Wyjście

- **Wejście:** ID folderu Drive, timestamp ostatniego udanego uruchomienia
  (`last_synced_at`). Folder ID **nie** jest daną seedowaną/w bazie — żyje w
  `.env` jako `GOOGLE_DRIVE_FOLDER_ID` (patrz tabela zmiennych niżej).
  `last_synced_at` to natomiast kolumna na `ACCOUNTS` ([[01-spec-data-model]])
  — mutowalny stan zapisywany przez węzeł `update_sync_cursor`, `NULL` do
  pierwszego przebiegu, nie seedowane.
- **Wyjście:** nowe wiersze w `STATEMENTS` ze statusem `pending`.

## Przechowywanie pobranych plików (zdecydowane: fetch-on-demand)

**Brak trwałej lokalnej kopii.** Drive jest już jedynym, trwałym źródłem
prawdy dla plików wyciągów — utrzymywanie drugiej kopii (filesystem/object
storage) byłoby zbędnym zdublowaniem. Zgodne z modelem danych: `STATEMENTS`
([[01-spec-data-model]]) ma tylko `drive_file_id` i `checksum`, celowo brak
kolumny na ścieżkę/URL lokalnego pliku.

Każdy węzeł/krok (w tym subworkflowy 03/04), który potrzebuje treści pliku,
pobiera ją ponownie z Drive po `drive_file_id` — bajty trzymane w pamięci
tylko na czas przetwarzania, nigdy nie zapisywane na dysk. `checksum`
(sha256 policzony przy każdym pobraniu) służy do wykrycia, czy plik na
Drive zmienił się między kolejnymi pobraniami tego samego `drive_file_id`.
Przy skali „kilka PDF-ów tygodniowo” ponowne pobieranie nie ma znaczenia
wydajnościowego.

## Kroki / węzły grafu (subgraph `ingestion`)

1. `list_new_files` — Drive API `files.list` z filtrem po `parents` i
   `modifiedTime > last_synced_at` (lub Drive Changes API dla większej
   niezawodności przy dużej liczbie plików — do wyboru w implementacji).
2. `dedupe_check` — porównanie `file_id` z istniejącymi `STATEMENTS.drive_file_id`;
   pominięcie już znanych plików.
3. `download` — pobranie treści pliku do pamięci (bez zapisu na dysk),
   obliczenie `sha256` checksum.
4. `persist_metadata` — insert do `STATEMENTS` (`account_id` na podstawie
   folderu źródłowego, `status = pending`). `period_start`/`period_end`/
   `opening_balance`/`closing_balance` pozostają `NULL` na tym etapie —
   ingestion nie parsuje treści PDF-a; te pola uzupełnia dopiero
   `extract_header_footer_balances` w kroku 2 weryfikacji ([[03-spec-statement-verification]]),
   stąd te kolumny są nullable w [[01-spec-data-model]].
5. `update_sync_cursor` — zapis nowego `last_synced_at`.

## Autoryzacja do Drive (zdecydowane)

**Ustalone: OAuth kontem osobistym użytkownika** (nie Service Account).
Interaktywny OAuth używany przez connector w tej sesji czatu (`Google
Drive` MCP) jest przypięty do konta użytkownika i sesji rozmowy — **nie
nadaje się** bezpośrednio do procesu bezobsługowego. Dla wdrożenia
produkcyjnego: jednorazowy, interaktywny consent OAuth (installed/web app w
Google Cloud Console) zwraca **refresh token długożyjący**, który backend
używa samodzielnie do odświeżania access tokenów bez ponownej interakcji
użytkownika.

Zmienne środowiskowe (wartości wyłącznie w `.env`, nigdy w kodzie/commitach/
czacie, zgodnie z regułą 6 z `CLAUDE.md`):

| Zmienna | Cel |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | Client ID z OAuth 2.0 Client (Google Cloud Console) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Client Secret odpowiadający powyższemu |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | Refresh token uzyskany z jednorazowego consentu |
| `GOOGLE_DRIVE_FOLDER_ID` | ID folderu Drive z wyciągami |

**Ważna pułapka operacyjna:** jeśli ekran zgody OAuth (OAuth consent
screen) ma status publikacji „Testing”, Google unieważnia refresh token po
7 dniach — co po tygodniu wyłączyłoby bezobsługowy proces. Trzeba ustawić
status publikacji na **„In production”** (dopuszczalne bez przechodzenia
weryfikacji Google dla pojedynczego, osobistego użytkownika — pojawi się
tylko ostrzeżenie „unverified app” przy jednorazowym consentcie, które
użytkownik akceptuje sam sobie).

## Zależności

- [[01-spec-data-model]] — tabela `STATEMENTS`.
- [[03-spec-statement-verification]] — konsumuje wynik tego kroku (ponownie
  pobiera plik po `drive_file_id`, patrz sekcja o fetch-on-demand wyżej).

## Otwarte kwestie

- Częstotliwość sprawdzania Drive: czy poll co tydzień zgodnie z
  harmonogramem raportu, czy częściej (np. codziennie), żeby błędy
  wykryć szybciej niż w dniu generowania raportu.

## Kryteria akceptacji / testy

- Test jednostkowy `dedupe_check` na fixture'ach z powtórzonym `file_id`.
- Test integracyjny na testowym folderze Drive: dodanie pliku → wykrycie →
  poprawny wpis w `STATEMENTS`.
- Test odporności na brak nowych plików (subgraph kończy się bez błędu,
  zero nowych wierszy).
- Test błędu autoryzacji (token wygasł) — subgraph zgłasza czytelny błąd,
  nie failuje w sposób cichy.
