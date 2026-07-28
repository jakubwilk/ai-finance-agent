# 12 — LLM Integration (Ollama / OVH)

## Cel

Zdefiniować, jak agent korzysta z modeli LLM hostowanych jako Ollama na
infrastrukturze OVH — bez żadnego dostawcy chmurowego (Anthropic/OpenAI) —
dla zadań: klasyfikacja kategorii, reasoning inwestycyjny, generowanie
treści narracyjnej raportu.

## Zakres

Wchodzi: konfiguracja klienta, wybór modelu per zadanie, obsługa
niezawodności (self-hosted, brak SLA dostawcy). Nie wchodzi: logika
biznesowa poszczególnych zadań (patrz [[06-spec-categorization]],
[[08-spec-investment-analysis]], [[09-spec-reporting]]).

## Integracja z LangChain/LangGraph

LangChain ma natywne wsparcie dla Ollama przez `langchain-ollama`
(`ChatOllama`), zgodne z resztą stosu `create_agent`/`StateGraph`. Ollama
udostępnia też endpoint kompatybilny z OpenAI API — alternatywna ścieżka
integracji przez `ChatOpenAI` ze zmienionym `base_url`, jeśli okaże się
wygodniejsza (np. dla structured output). Ostateczny wybór do potwierdzenia
przy implementacji na podstawie aktualnej dokumentacji `langchain-ollama`
(nie zgadywać z pamięci — sprawdzić `docs.langchain.com`).

## Zadania korzystające z LLM

| Zadanie | Spec | Wymaganie |
|---|---|---|
| Klasyfikacja kategorii transakcji | [[06-spec-categorization]] | structured output (kategoria + confidence), niska latencja (dużo transakcji per wyciąg) |
| Reasoning inwestycyjny | [[08-spec-investment-analysis]] | wolniejsze, bardziej „rozumujące” wywołanie, mniejszy wolumen |
| Treść narracyjna raportu | [[09-spec-reporting]] | generowanie tekstu, styl komunikacyjny |

Różne zadania mogą używać różnych modeli (np. mniejszy/szybszy model do
klasyfikacji masowej, większy do reasoningu inwestycyjnego) — konfigurowalne
per zadanie, nie jeden model na cały system.

## Zdecydowane: format zmiennych środowiskowych

Konkretne wartości (URL endpointu, nazwy modeli) uzupełni użytkownik
bezpośrednio w `.env` — nie są przekazywane w czacie/kodzie/commitach,
zgodnie z regułą 6 z `CLAUDE.md`. Format:

| Zmienna | Cel |
|---|---|
| `OLLAMA_BASE_URL` | adres endpointu Ollama na OVH |
| `OLLAMA_MODEL_CLASSIFICATION` | model użyty do klasyfikacji kategorii ([[06-spec-categorization]]) |
| `OLLAMA_MODEL_INVESTMENT` | model użyty do reasoningu inwestycyjnego ([[08-spec-investment-analysis]]) |
| `OLLAMA_MODEL_REPORTING` | model użyty do treści narracyjnej raportu ([[09-spec-reporting]]) |
| `OLLAMA_API_KEY` | opcjonalna — puste, jeśli endpoint nie wymaga uwierzytelnienia |

Trzy osobne zmienne modelu pokrywają też pytanie „czy jeden model
wystarczy do wszystkiego": jeśli tak, użytkownik wpisze tę samą nazwę we
wszystkie trzy.

## Niezawodność (self-hosted, brak SLA)

- Timeout i retry z backoff na każde wywołanie (self-hosted Ollama może być
  wolniejsze pod obciążeniem niż API komercyjne).
- Fallback przy niedostępności modelu: dla kategoryzacji — transakcja
  trafia do `needs_review` zamiast failować cały graf (patrz
  [[06-spec-categorization]]); dla reasoningu inwestycyjnego/raportu —
  ewentualne opóźnienie raportu z jasnym komunikatem, zamiast wysyłki
  niekompletnych danych.
- Monitoring dostępności endpointu Ollama jako część health-checków
  backendu (patrz [[13-spec-backend-api]]).

## Zależności

- [[06-spec-categorization]], [[08-spec-investment-analysis]],
  [[09-spec-reporting]] — konsumenci.
- [[15-spec-deployment-coolify]] — sieciowe połączenie do endpointu OVH
  (adres, ewentualny VPN/firewall, sekrety jeśli endpoint wymaga
  uwierzytelnienia).

## Otwarte kwestie (blokujące implementację — nie zgaduję)

- **Konkretne wartości** zmiennych środowiskowych powyżej (URL endpointu,
  nazwy/warianty modeli faktycznie dostępnych na instancji OVH, ich limity
  kontekstu) — mechanizm ustalony, wartości do uzupełnienia przez
  użytkownika w `.env`.
- Oczekiwana przepustowość (ile transakcji tygodniowo realistycznie trafi
  do klasyfikacji LLM) — wpływa na to, czy potrzebne jest batchowanie
  wywołań.

## Kryteria akceptacji / testy

- Test połączenia z endpointem Ollama (health check) w środowisku dev.
- Test structured output dla klasyfikacji — odpowiedź modelu poprawnie
  parsuje się do `category + confidence` zgodnie ze schematem Pydantic
  (patrz `langchain-middleware`).
- Test zachowania przy timeout/niedostępności endpointu — graf nie
  crashuje, transakcja/raport trafia na ścieżkę fallback zamiast utraty
  danych.
