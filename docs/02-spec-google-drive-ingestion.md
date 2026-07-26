# 02 — Google Drive Ingestion

## Cel

Wykryć i pobrać nowe wyciągi bankowe wgrywane przez użytkownika na Dysk
Google, zanim jakikolwiek dalszy krok (weryfikacja, ekstrakcja) się zacznie.

## Zakres

Wchodzi: monitorowanie folderów Drive, pobieranie nowych plików PDF, zapis
metadanych w `STATEMENTS`. Nie wchodzi: parsowanie zawartości pliku (patrz
[[04-spec-transaction-extraction]]) ani walidacja poprawności (patrz
[[03-spec-statement-verification]]).

## Struktura Drive (ustalona)

Jeden wspólny folder root z podfolderami per typ konta:

```
/Wyciągi
  /Prywatne
  /Firmowe
```

Każdy nowy wyciąg trafia jako pojedynczy plik PDF do odpowiedniego
podfolderu. Nazewnictwo plików nie jest ujednolicone z góry — subworkflow
nie polega na parsowaniu nazwy pliku, tylko na treści (patrz
[[04-spec-transaction-extraction]]).

## Wejście / Wyjście

- **Wejście:** ID folderów Drive (`Prywatne`, `Firmowe`), timestamp
  ostatniego udanego uruchomienia (`last_synced_at` per folder).
- **Wyjście:** nowe wiersze w `STATEMENTS` ze statusem `pending`, plik
  pobrany do lokalnego/obiektowego storage roboczego (do ustalenia:
  filesystem kontenera vs. bucket — patrz [[15-spec-deployment-coolify]]).

## Kroki / węzły grafu (subgraph `ingestion`)

1. `list_new_files` — Drive API `files.list` z filtrem po `parents` i
   `modifiedTime > last_synced_at` (lub Drive Changes API dla większej
   niezawodności przy dużej liczbie plików — do wyboru w implementacji).
2. `dedupe_check` — porównanie `file_id` z istniejącymi `STATEMENTS.drive_file_id`;
   pominięcie już znanych plików.
3. `download` — pobranie treści pliku, obliczenie `sha256` checksum.
4. `persist_metadata` — insert do `STATEMENTS` (`account_id` na podstawie
   folderu źródłowego, `status = pending`).
5. `update_sync_cursor` — zapis nowego `last_synced_at`.

## Autoryzacja do Drive (otwarta kwestia — krytyczna)

Interaktywny OAuth używany przez connector w tej sesji czatu (`Google
Drive` MCP) jest przypięty do konta użytkownika i sesji rozmowy — **nie
nadaje się** do procesu bezobsługowego działającego cyklicznie na serwerze.
Dla wdrożenia produkcyjnego potrzebne jest jedno z:

- **Service Account** z dostępem do współdzielonego folderu (Shared Drive
  lub folder udostępniony kontu serwisowemu) — rekomendowane dla procesu
  bezobsługowego, brak wygasających tokenów użytkownika.
- OAuth z refresh tokenem długożyjącym, przechowywanym jako sekret.

**Do ustalenia z użytkownikiem przed implementacją** — nie zakładam żadnej
z opcji z góry.

## Zależności

- [[01-spec-data-model]] — tabela `STATEMENTS`.
- [[03-spec-statement-verification]] — konsumuje wynik tego kroku.
- [[15-spec-deployment-coolify]] — gdzie fizycznie ląduje pobrany plik.

## Otwarte kwestie

- Metoda autoryzacji serwerowej do Drive (service account vs. OAuth
  refresh token).
- Miejsce przechowywania pobranych plików PDF (filesystem kontenera z
  wolumenem trwałym vs. object storage).
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
