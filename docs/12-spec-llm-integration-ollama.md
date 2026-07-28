# 12 — LLM Integration (OVH AI Endpoints)

## Cel

Zdefiniować, jak agent korzysta z modeli LLM hostowanych na **OVH AI
Endpoints** — bez żadnego dostawcy chmurowego (Anthropic/OpenAI) — dla
zadań: klasyfikacja kategorii, reasoning inwestycyjny, generowanie treści
narracyjnej raportu.

**Korekta:** pierwotnie zakładano self-hosted Ollama na infrastrukturze
OVH. Użytkownik potwierdził, że faktycznie używa **OVH AI Endpoints**
(zdecydowane) — zweryfikowane bezpośrednio na żywym katalogu
(`https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models`, bez
autoryzacji): to serverless API **kompatybilne z OpenAI** (Llama, Qwen,
Mistral, gpt-oss i inne, rozliczane per token), nie surowy protokół
Ollama.

## Zakres

Wchodzi: konfiguracja klienta, wybór modelu per zadanie, obsługa
niezawodności (serverless, ale wciąż zewnętrzne wywołanie sieciowe bez
gwarancji). Nie wchodzi: logika biznesowa poszczególnych zadań (patrz
[[06-spec-categorization]], [[08-spec-investment-analysis]],
[[09-spec-reporting]]).

## Integracja z LangChain/LangGraph

**Zdecydowane:** `langchain_openai.ChatOpenAI` z niestandardowym `base_url`
(nie `langchain-ollama`/`ChatOllama` — to była błędna wcześniejsza
architektura, patrz korekta wyżej). Potwierdzone względem aktualnej
dokumentacji `docs.langchain.com` (nie z pamięci):
`ChatOpenAI(model=, base_url=, api_key=, timeout=, max_retries=)` —
`timeout`/`max_retries` realizują wymóg „timeout i retry z backoff” niżej
natywnie, bez własnej logiki retry. Implementacja:
`backend/src/finance_agent/llm/client.py` (`build_chat_model` +
`build_classification_model`/`build_investment_model`/
`build_reporting_model`).

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
| `OVH_AI_ENDPOINTS_BASE_URL` | adres endpointu OVH AI Endpoints (OpenAI-compatible) |
| `OVH_AI_ENDPOINTS_API_KEY` | klucz API do OVH AI Endpoints |
| `OVH_MODEL_CLASSIFICATION` | model użyty do klasyfikacji kategorii ([[06-spec-categorization]]) |
| `OVH_MODEL_INVESTMENT` | model użyty do reasoningu inwestycyjnego ([[08-spec-investment-analysis]]) |
| `OVH_MODEL_REPORTING` | model użyty do treści narracyjnej raportu ([[09-spec-reporting]]) |

Dostępne w danej chwili modele (id, cena, kontekst): żywy katalog
`https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models` (bez
autoryzacji) — źródło prawdy zamiast zgadywania z pamięci, bo katalog OVH
się zmienia.

Trzy osobne zmienne modelu pokrywają też pytanie „czy jeden model
wystarczy do wszystkiego": jeśli tak, użytkownik wpisze tę samą nazwę we
wszystkie trzy.

## Niezawodność

- Timeout (60s) i `max_retries` (3, z wbudowanym backoffem `langchain_openai`)
  na każde wywołanie — zaimplementowane w `build_chat_model`. Serverless
  API OVH nie jest już „self-hosted, może zwolnić pod obciążeniem”, ale
  to nadal zewnętrzne wywołanie sieciowe bez gwarancji, więc retry zostaje.
- Fallback przy niedostępności modelu: dla kategoryzacji — transakcja
  trafia do `needs_review` zamiast failować cały graf (patrz
  [[06-spec-categorization]]); dla reasoningu inwestycyjnego/raportu —
  ewentualne opóźnienie raportu z jasnym komunikatem, zamiast wysyłki
  niekompletnych danych. (Logika tego fallbacku należy do tamtych kroków —
  `llm/client.py` dostarcza tylko klienta.)
- Monitoring dostępności endpointu OVH AI Endpoints jako część
  health-checków backendu (patrz [[13-spec-backend-api]]).

## Zależności

- [[06-spec-categorization]], [[08-spec-investment-analysis]],
  [[09-spec-reporting]] — konsumenci.
- [[15-spec-deployment-coolify]] — sieciowe połączenie do endpointu OVH
  (adres, ewentualny VPN/firewall, sekrety jeśli endpoint wymaga
  uwierzytelnienia).

## Otwarte kwestie

- Oczekiwana przepustowość (ile transakcji tygodniowo realistycznie trafi
  do klasyfikacji LLM) — wpływa na to, czy potrzebne jest batchowanie
  wywołań.

## Kryteria akceptacji / testy

Krok „fundament” (ten dokument, konstrukcja klienta) — bez realnego
wywołania OVH API w testach, ten sam wzorzec co Drive/pdfplumber gdzie
indziej w repo:

- Test `build_chat_model` zgłasza czytelny błąd nazywający brakującą
  zmienną, gdy `OVH_AI_ENDPOINTS_BASE_URL`/`_API_KEY`/nazwa modelu nie są
  ustawione.
- Test `build_chat_model` konstruuje `ChatOpenAI` z oczekiwanym
  `base_url`/`api_key`/`model`/`timeout`/`max_retries`.
- Test `build_classification_model`/`build_investment_model`/
  `build_reporting_model` używają właściwego pola `settings.ovh_model_*`.

Testy structured output / zachowania przy timeout na prawdziwym wywołaniu
należą do konsumentów (`docs/06`, `docs/08`, `docs/09`), nie do tego
kroku-fundamentu.
