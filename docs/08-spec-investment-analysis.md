# 08 — Investment Analysis

## Cel

Przeanalizować nadwyżkę finansową (surplus) wyliczoną w
[[07-spec-cashflow-calculation]] i zaproponować użytkownikowi, jak część
tych środków mogłaby zostać zainwestowana.

## Zakres

Wchodzi: logika analizy surplusu i generowania propozycji alokacji. Nie
wchodzi: wykonywanie jakichkolwiek operacji finansowych — agent **wyłącznie
sugeruje**, nigdy nie składa zleceń ani nie przenosi środków (założenie
robocze, do potwierdzenia jako jawna decyzja bezpieczeństwa, nie tylko
domyślne założenie).

## Wejście / Wyjście

- **Wejście:** `surplus`, historia surplusów z poprzednich okresów (do
  oceny trendu/stabilności, nie tylko jednorazowego wyniku), ewentualnie
  bufor bezpieczeństwa (poduszka finansowa) — patrz otwarte kwestie.
- **Wyjście:** `INVESTMENT_RECOMMENDATIONS` (kwota, uzasadnienie,
  `allocation_proposal` jako propozycja podziału), konsumowane przez
  [[09-spec-reporting]].

## Kroki / węzły grafu (subgraph `investment_analysis`)

1. `check_safety_buffer` — czy po odjęciu nadwyżki od bieżących środków
   zostaje wystarczająca poduszka bezpieczeństwa (kwota/liczba miesięcy
   wydatków) — jeśli nie, sugerowana kwota do inwestycji jest pomniejszona
   lub zerowa, z wyjaśnieniem w raporcie.
2. `assess_trend` — czy surplus jest stabilny w czasie (kilka ostatnich
   okresów), czy to jednorazowa anomalia (np. wpływ zwrotu podatku) — wpływa
   na ostrożność rekomendacji.
3. `generate_allocation_proposal` — reguły + reasoning LLM (Ollama, patrz
   [[12-spec-llm-integration-ollama]]) generujące sugestię podziału kwoty
   między dostępne instrumenty, z uzasadnieniem tekstowym.
4. `persist_recommendation` — zapis do `INVESTMENT_RECOMMENDATIONS`.

## Otwarte kwestie (blokujące pełną implementację — nie zgaduję)

- **Profil ryzyka użytkownika** — konserwatywny / zbalansowany / agresywny?
  Wpływa bezpośrednio na logikę `generate_allocation_proposal`.
- **Dostępne instrumenty inwestycyjne**, które w ogóle mają być brane pod
  uwagę — np. ETF-y, obligacje skarbowe, lokaty, konto oszczędnościowe,
  IKE/IKZE, inne. Bez tej listy propozycja nie ma z czego wybierać.
- **Wielkość poduszki bezpieczeństwa** (safety buffer) przed sugerowaniem
  inwestowania nadwyżki — np. „X miesięcy wydatków stałych zostaje
  nietknięte”.
- **Zakres automatyzacji** — potwierdzenie, że agent ma tylko sugerować
  (tekstowo/liczbowo w raporcie), a nie integrować się z żadnym
  maklerskim/bankowym API do wykonania operacji. Założenie robocze na razie:
  wyłącznie sugestia.

## Zależności

- [[07-spec-cashflow-calculation]] — dostarcza `surplus`.
- [[12-spec-llm-integration-ollama]] — reasoning tekstowy.
- [[09-spec-reporting]] — konsumuje rekomendację do treści raportu.
- [[01-spec-data-model]] — `INVESTMENT_RECOMMENDATIONS`.

## Kryteria akceptacji / testy

*(część kryteriów zależy od rozstrzygnięcia otwartych kwestii powyżej —
placeholder do uzupełnienia po ustaleniu profilu ryzyka i instrumentów)*

- Test `check_safety_buffer`: surplus mniejszy niż próg bezpieczeństwa →
  rekomendacja zerowa lub zredukowana, z jawnym uzasadnieniem w treści.
- Test `assess_trend`: pojedynczy nietypowo wysoki surplus (odstający od
  historii) → ostrzeżenie o możliwej anomalii zamiast pełnej rekomendacji.
- Test end-to-end na fixture'ach z historycznymi surplusami → deterministyczna
  część logiki (safety buffer, trend) daje powtarzalny wynik niezależnie od
  LLM.
