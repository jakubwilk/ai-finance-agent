# 13 — Backend API

## Cel

Wystawić lokalny FastAPI backend jako jedyny pośrednik między React UI a
master grafem LangGraph — bez jakiegokolwiek konta chmurowego
(LangSmith/LangGraph Studio wykluczone zgodnie z decyzją w `CLAUDE.md`).

## Zakres

Wchodzi: endpointy do triggerowania runów, listy wątków, historii stanu,
struktury grafu, health-checki. Nie wchodzi: logika samego pipeline'u
(patrz [[11-spec-orchestration-scheduling]]) ani UI (patrz
[[14-spec-frontend-ui]]).

## Endpointy (projekt wstępny)

| Metoda | Ścieżka | Cel |
|---|---|---|
| `GET` | `/graph/structure` | zwraca `graph.get_graph().draw_mermaid()` master grafu |
| `POST` | `/runs` | ręczne wywołanie master grafu (np. „uruchom teraz” zamiast czekać na cron) |
| `GET` | `/runs` | lista `thread_id` (uruchomień) z podstawowym statusem |
| `GET` | `/runs/{thread_id}/state` | bieżący stan grafu dla wątku |
| `GET` | `/runs/{thread_id}/history` | `get_state_history` — pełna historia kroków/checkpointów |
| `POST` | `/runs/{thread_id}/resume` | wznowienie po `interrupt()` (`Command(resume=...)`) — używane przez `human_review` w [[06-spec-categorization]] |
| `GET` | `/health` | status backendu + dostępność bazy + dostępność endpointu Ollama |

## Zależności

- [[11-spec-orchestration-scheduling]] — master graph, którym ten backend
  steruje.
- [[06-spec-categorization]] — `resume` obsługuje decyzje human-in-the-loop.
- [[14-spec-frontend-ui]] — konsument tego API.
- [[01-spec-data-model]] — odczyt danych domenowych do wzbogacenia
  odpowiedzi (np. podgląd transakcji `needs_review`).

## Bezpieczeństwo

Backend nie jest wystawiony publicznie bez uwierzytelnienia — dostęp tylko
z sieci lokalnej/wewnętrznej Coolify lub za prostym uwierzytelnieniem (do
ustalenia, patrz otwarte kwestie). Dane finansowe wrażliwe → żadnych
sekretów (SMTP, Drive, DB) w odpowiedziach API.

## Otwarte kwestie

- Czy backend wymaga własnego uwierzytelnienia (np. prosty API key/basic
  auth), skoro UI ma być lokalne/prywatne, czy wystarczy izolacja sieciowa
  w topologii Coolify.
- Czy `POST /runs` ma wspierać wybór konkretnego konta
  (private/company) czy zawsze oba na raz.

## Kryteria akceptacji / testy

- Test `GET /graph/structure` zwraca poprawny Mermaid, renderowalny bez
  błędów w UI.
- Test `POST /runs` → `GET /runs/{thread_id}/state` pokazuje postęp
  uruchomienia.
- Test `resume` po `interrupt()` poprawnie wznawia zawieszony graf.
- Test `/health` poprawnie raportuje niedostępność bazy/Ollama gdy są
  wyłączone (np. w środowisku testowym z mockami wyłączonymi celowo).
