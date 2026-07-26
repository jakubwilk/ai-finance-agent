# 16 — Testing Strategy

## Cel

Zdefiniować, jak każdy subworkflow (02–11) i warstwa wspierająca (12–15)
będą testowane, zgodnie z zasadą z `CLAUDE.md`: „Every feature needs
tests. Nothing is considered done without tests that prove the use case
was actually analyzed and verified.”

## Zakres

Wchodzi: podejście do testów per warstwa, fixture'y, granice mockowania.
Nie wchodzi: konkretne przypadki testowe per subworkflow — te są już
wymienione w sekcji „Kryteria akceptacji / testy” każdej odpowiedniej
specyfikacji (02–15); ten dokument definiuje wspólną strategię, nie
duplikuje listy.

## Piramida testów dla tego projektu

1. **Testy jednostkowe** — czyste funkcje bez I/O: normalizacja pól
   transakcji ([[04-spec-transaction-extraction]]), reguły dopasowania
   kategorii ([[06-spec-categorization]]), wyliczenia bilansu
   ([[07-spec-cashflow-calculation]]), logika safety-buffer
   ([[08-spec-investment-analysis]]).
2. **Testy z fixture'ami** — dla parserów PDF: zestaw przykładowych
   wyciągów (zanonimizowanych/testowych, nigdy prawdziwych danych
   finansowych użytkownika w repozytorium) z oczekiwanym „złotym” wynikiem
   ekstrakcji (snapshot testing), patrz
   [[04-spec-transaction-extraction]].
3. **Testy integracyjne z mockami zewnętrznych usług** — Google Drive,
   SMTP, Ollama mockowane (np. `respx`/`unittest.mock` dla HTTP), żeby testy
   grafu ([[11-spec-orchestration-scheduling]]) nie zależały od
   rzeczywistych usług zewnętrznych i mogły biec w CI bez sekretów
   produkcyjnych.
4. **Test end-to-end lokalny** — pełny przebieg master grafu na
   fixture'ach, weryfikujący że dane płyną poprawnie przez wszystkie
   subgraphs od `ingestion` do `email_delivery` (patrz
   [[11-spec-orchestration-scheduling]]).
5. **Testy human-in-the-loop** — `interrupt()`/`Command(resume=...)` testowane
   explicite jako osobny przypadek (nie tylko happy path bez przerwań),
   patrz [[06-spec-categorization]].

## Dane testowe

- Żadnych prawdziwych wyciągów bankowych użytkownika w repozytorium —
  wyłącznie zanonimizowane/syntetyczne fixture'y PDF z fikcyjnymi kwotami i
  danymi.
- Tabele `CATEGORIES`/`FIXED_COSTS` w testach wypełnione danymi testowymi
  niezależnie od rzeczywistej zawartości, którą dostarczy użytkownik
  później.

## Zależności

Dotyczy wszystkich specyfikacji 02–15 — każda z nich ma już własną sekcję
„Kryteria akceptacji / testy” zgodną z zasadami tego dokumentu.

## Otwarte kwestie

- Narzędzie do testów Python — do potwierdzenia przy implementacji (np.
  `pytest`, zgodnie z bieżącymi dobrymi praktykami 2026 — sprawdzić przed
  wyborem, nie zakładać z pamięci).
- Czy potrzebne jest CI (np. GitHub Actions) uruchamiające testy
  automatycznie przy każdym PR — do ustalenia, gdy repozytorium trafi na
  zdalny hosting Git.

## Kryteria akceptacji

- Każdy subworkflow 02–11 ma co najmniej jeden test jednostkowy i jeden
  test na fixture'ach/integracyjny przed uznaniem za „gotowe” zgodnie z
  regułą z `CLAUDE.md`.
- Testy nie wymagają rzeczywistych sekretów (Drive/SMTP/Ollama) do
  uruchomienia lokalnie — wszystko mockowane lub fixture'owane.
