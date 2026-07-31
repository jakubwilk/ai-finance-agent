# 10 — Email Delivery

## Cel

Wysłać wygenerowane raporty (tygodniowe, miesięczne, oraz alerty o błędach
w wyciągach) na maila użytkownika przez SMTP.

## Zakres

Wchodzi: wysyłka SMTP, obsługa błędów wysyłki, retry. Nie wchodzi:
generowanie treści (patrz [[09-spec-reporting]]).

## Wejście / Wyjście

- **Wejście:** `REPORTS` ze statusem `pending` i wypełnionym
  `content_html`; osobno — zdarzenia alertu z
  [[03-spec-statement-verification]] (błąd w wyciągu, wysyłany od razu, nie
  czekając na raport tygodniowy).
- **Wyjście:** `REPORTS.delivery_status` → `sent` lub `failed`,
  `sent_at`.

## Mechanizm (ustalony: SMTP)

- Wysyłka przez standardowe SMTP — **zdecydowane: `aiosmtplib`** (async,
  zatwierdzone przez użytkownika przed dodaniem jako zależność, zgodnie z
  regułą 7 `CLAUDE.md`; sprawdzone bezpośrednio w dokumentacji
  `aiosmtplib.readthedocs.io`, nie z pamięci). Wysokopoziomowe API:
  `aiosmtplib.send(message, hostname=, port=, username=, password=,
  start_tls=True)`, gdzie `message` to standardowy
  `email.message.EmailMessage`.
- Dane dostępowe SMTP (host, port, użytkownik, hasło/app-password) — **w
  `.env`, nigdy w kodzie/dokumentacji/commitach**, zgodnie z zasadą
  „Never handle secrets in plaintext” z `CLAUDE.md`. Puste `.env` nie
  blokuje budowy/testów tego kroku — ten sam precedens co
  `GOOGLE_OAUTH_*` (krok 1) i `OVH_AI_ENDPOINTS_*` (krok 5): kod buduje się
  i testuje w pełni z wstrzykiwanym fake'owym klientem SMTP, realne
  wartości uzupełnia użytkownik sam przed realnym uruchomieniem.

## Zdecydowane: format zmiennych środowiskowych

Konkretne wartości uzupełni użytkownik bezpośrednio w `.env` — nigdy w
czacie/kodzie/commitach, zgodnie z regułą 6 z `CLAUDE.md`. Format
niezależny od konkretnego dostawcy SMTP (Gmail, SES, Mailgun, Postmark,
własny serwer — działa identycznie dla każdego z nich):

| Zmienna | Cel |
|---|---|
| `SMTP_HOST` | host serwera SMTP |
| `SMTP_PORT` | port serwera SMTP |
| `SMTP_USER` | użytkownik/login SMTP |
| `SMTP_PASSWORD` | hasło / app-password SMTP |
| `REPORT_RECIPIENT_EMAIL` | odbiorca raportów |

## Kroki / węzły grafu (subgraph `email_delivery`)

1. `render_final_payload` — `Report` gdzie `delivery_status == "pending"`;
   MIME multipart (HTML + statyczny plain-text fallback, bez pełnego
   html→text parsera — poza zakresem) z treścią raportu.
2. `send_smtp` — połączenie do serwera SMTP (TLS), wysyłka. **Retry —
   otwarta kwestia rozstrzygnięta:** 3 próby z rosnącym krótkim odstępem
   (zaproponowana w tej specyfikacji wartość domyślna, przyjęta wprost —
   ten sam tryb co tolerancja zaokrągleń w
   [[03-spec-statement-verification]]).
3. `handle_result` — sukces → `delivery_status = sent`, `sent_at = now()`;
   błąd (po wyczerpaniu prób) → `delivery_status = failed`, bez dalszego
   retry w kolejnych przebiegach (następny tydzień tworzy nowe wiersze
   `Report`, nie ponawia starych — świadome ograniczenie, ten sam wzorzec
   co osierocone `INVESTMENT_RECOMMENDATIONS.report_id` w
   [[09-spec-reporting]]).
4. `alert_immediate` — **nie jest częścią tego subgraphu.** Diagram w
   [[11-spec-orchestration-scheduling]] rysuje go jako pojedynczy węzeł
   master grafu (`ALERT[[alert_immediate]]`), nie zagnieżdżony subgraph —
   zaimplementowany bezpośrednio jako funkcja w `graph/master.py`
   (`_alert_immediate_node`), bez sesji DB (nic nie zapisuje). Treść błędu
   (`statement_id`/`failure_reason`) pochodzi z nowego pola
   `MasterGraphState.alert_details`, ustawianego przez węzły
   `verification_pre_check`/`verification_post_check` gdy wykryją błąd —
   ta sama zasada co już istniejące `verification_ok`/`needs_review`
   (dane "wyniku tego przebiegu", nie nowa kolumna/tabela do śledzenia
   "już zaalarmowano").

## Zależności

- [[09-spec-reporting]] — dostarcza treść do wysyłki.
- [[03-spec-statement-verification]] — źródło alertów natychmiastowych.
- [[01-spec-data-model]] — `REPORTS.delivery_status`.
- [[15-spec-deployment-coolify]] — sekrety SMTP jako zmienne środowiskowe.

## Otwarte kwestie

- ~~Polityka retry...~~ — **zdecydowane: 3 próby**, patrz „Kroki / węzły
  grafu” wyżej.

## Kryteria akceptacji / testy

- Test wysyłki na testowym serwerze SMTP (np. `mailhog`/`smtp4dev` lokalnie
  w środowisku testowym) — mail dociera z poprawną treścią.
- Test obsługi błędu (serwer SMTP niedostępny) — `delivery_status = failed`,
  brak nieobsłużonego wyjątku w grafie.
- Test alertu natychmiastowego: błąd weryfikacji wyciągu wywołuje wysyłkę
  bez czekania na harmonogram tygodniowy.
