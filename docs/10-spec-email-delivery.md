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

- Wysyłka przez standardowe SMTP (biblioteka do wyboru w implementacji —
  np. `aiosmtplib` dla wersji asynchronicznej zgodnej z resztą stosu
  FastAPI/LangGraph, do zweryfikowania w dokumentacji przy pisaniu kodu).
- Dane dostępowe SMTP (host, port, użytkownik, hasło/app-password) — **w
  `.env`, nigdy w kodzie/dokumentacji/commitach**, zgodnie z zasadą
  „Never handle secrets in plaintext” z `CLAUDE.md`.

## Kroki / węzły grafu (subgraph `email_delivery`)

1. `render_final_payload` — MIME multipart (HTML + ewentualny plain-text
   fallback) z treścią raportu.
2. `send_smtp` — połączenie do serwera SMTP (TLS), wysyłka.
3. `handle_result` — sukces → `delivery_status = sent`, `sent_at = now()`;
   błąd → `delivery_status = failed`, retry z backoff (liczba prób do
   ustalenia, np. 3).
4. `alert_immediate` (ścieżka równoległa, poza cyklem raportowym) — dla
   błędów wykrytych w [[03-spec-statement-verification]], wysyłka
   natychmiastowego, krótkiego maila z opisem problemu.

## Zależności

- [[09-spec-reporting]] — dostarcza treść do wysyłki.
- [[03-spec-statement-verification]] — źródło alertów natychmiastowych.
- [[01-spec-data-model]] — `REPORTS.delivery_status`.
- [[15-spec-deployment-coolify]] — sekrety SMTP jako zmienne środowiskowe.

## Otwarte kwestie

- Adres(y) odbiorcy raportów — jeden mail czy różni odbiorcy dla
  prywatnego/firmowego konta.
- Dostawca SMTP (Gmail SMTP z app-password, inny dostawca transakcyjny typu
  SES/Mailgun/Postmark, czy własny serwer pocztowy) — wpływa na limity
  wysyłki i reputację nadawcy; do ustalenia.
- Polityka retry przy nieudanej wysyłce (liczba prób, odstępy).

## Kryteria akceptacji / testy

- Test wysyłki na testowym serwerze SMTP (np. `mailhog`/`smtp4dev` lokalnie
  w środowisku testowym) — mail dociera z poprawną treścią.
- Test obsługi błędu (serwer SMTP niedostępny) — `delivery_status = failed`,
  brak nieobsłużonego wyjątku w grafie.
- Test alertu natychmiastowego: błąd weryfikacji wyciągu wywołuje wysyłkę
  bez czekania na harmonogram tygodniowy.
