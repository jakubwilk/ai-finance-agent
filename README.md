# AI Finance Agent

Agent automatyzujący cotygodniową analizę finansów prywatnych:
odbiera wyciągi bankowe wgrywane na Dysk Google, weryfikuje ich poprawność,
wyciąga z nich transakcje, kategoryzuje je, wylicza bilans
przychodów/wydatków, proponuje alokację nadwyżki na inwestycje i wysyła
raport (tygodniowy i miesięczny) mailem.

## Status projektu

Repozytorium jest na etapie **specyfikacji** — kod jeszcze nie istnieje.
Pełny opis architektury, diagram workflowów i uzasadnienie wyboru
technologii: [`docs/00-spec-overview-architecture.md`](docs/00-spec-overview-architecture.md).

## Stos technologiczny

| Warstwa | Wybór |
|---|---|
| Backend / logika agenta | Python |
| Orkiestracja | LangGraph |
| UI | React |
| Komponenty UI | shadcn/ui (Tailwind + Radix/Base UI) |
| API pośredniczące | FastAPI |
| Baza danych | PostgreSQL — lokalnie i w każdym środowisku (dev/prod) |
| LLM | OVH AI Endpoints (serverless, OpenAI-compatible) |
| Deploy | Docker + Coolify |

Szczegóły i uzasadnienie: [`docs/00-spec-overview-architecture.md`](docs/00-spec-overview-architecture.md).

## Specyfikacje (`docs/`)

| # | Plik | Zakres |
|---|---|---|
| 00 | [overview-architecture](docs/00-spec-overview-architecture.md) | architektura całości, diagram workflowów, mapa specyfikacji |
| 01 | [data-model](docs/01-spec-data-model.md) | schemat bazy danych |
| 02 | [google-drive-ingestion](docs/02-spec-google-drive-ingestion.md) | pobieranie nowych wyciągów z Dysku Google |
| 03 | [statement-verification](docs/03-spec-statement-verification.md) | walidacja poprawności wyciągu (salda, duplikaty) |
| 04 | [transaction-extraction](docs/04-spec-transaction-extraction.md) | parsowanie linii transakcji z PDF |
| 05 | [fixed-costs](docs/05-spec-fixed-costs.md) | koszty stałe i dopasowanie do transakcji |
| 06 | [categorization](docs/06-spec-categorization.md) | przypisanie kategorii (reguły + LLM + review) |
| 07 | [cashflow-calculation](docs/07-spec-cashflow-calculation.md) | bilans przychodów/wydatków, nadwyżka |
| 08 | [investment-analysis](docs/08-spec-investment-analysis.md) | propozycja alokacji nadwyżki |
| 09 | [reporting](docs/09-spec-reporting.md) | treść raportu tygodniowego/miesięcznego |
| 10 | [email-delivery](docs/10-spec-email-delivery.md) | wysyłka raportów przez SMTP |
| 11 | [orchestration-scheduling](docs/11-spec-orchestration-scheduling.md) | master graph LangGraph + harmonogram |
| 12 | [llm-integration-ollama](docs/12-spec-llm-integration-ollama.md) | integracja z OVH AI Endpoints |
| 13 | [backend-api](docs/13-spec-backend-api.md) | FastAPI dla UI (trigger, historia, stan grafu) |
| 14 | [frontend-ui](docs/14-spec-frontend-ui.md) | React UI (graf, historia, review kategoryzacji) |
| 15 | [deployment-coolify](docs/15-spec-deployment-coolify.md) | topologia Docker/Coolify |
| 16 | [testing-strategy](docs/16-spec-testing-strategy.md) | strategia testów |

## Zasady pracy nad projektem

Zasady niepodlegające negocjacji (m.in. Plan Mode przed każdą zmianą, brak
fabrykowania danych, testy do każdej funkcjonalności, tylko oficjalne
biblioteki) są opisane w [`CLAUDE.md`](CLAUDE.md).

## Otwarte kwestie blokujące start implementacji

- **Profil ryzyka i dostępne instrumenty inwestycyjne** —
  [`08-spec-investment-analysis`](docs/08-spec-investment-analysis.md).
- **Konkretne wartości SMTP i adresów odbiorców raportów** (format
  zmiennych środowiskowych już ustalony) —
  [`10-spec-email-delivery`](docs/10-spec-email-delivery.md).

Pełna lista otwartych kwestii per obszar znajduje się w sekcji „Otwarte
kwestie” każdej specyfikacji.
