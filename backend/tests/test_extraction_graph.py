from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from finance_agent.db.models import Account, Statement, Transaction
from finance_agent.subgraphs.extraction.graph import build_extraction_graph
from finance_agent.subgraphs.extraction.parsers.base import RawTransaction
from finance_agent.subgraphs.extraction.parsers.generic import GenericLineParser
from finance_agent.subgraphs.extraction.parsers.pko_bp import (
    PkoBpHistoriaRachunkuParser,
)

# Column x0 anchors matching pko_bp.py's real, empirically-confirmed
# thresholds — one "word" per populated column is enough since the parser
# just joins same-column words with spaces.
_X0 = {
    "data_operacji": 10.0,
    "data_waluty": 95.0,
    "typ_transakcji": 140.0,
    "opis": 210.0,
    "kwota": 460.0,
    "saldo": 520.0,
}


def _row(top: float, **columns: str) -> list[dict]:
    return [
        {"text": text, "x0": _X0[column], "top": top}
        for column, text in columns.items()
        if text
    ]


PKO_BP_FIRST_PAGE_TEXT = (
    "Powszechna Kasa Oszczędności Bank Polski SA\n"
    "HISTORIA RACHUNKU\n"
    "Zastosowane kryteria wyboru"
)


def test_matches_identifies_pko_bp_export():
    parser = PkoBpHistoriaRachunkuParser()
    assert parser.matches(PKO_BP_FIRST_PAGE_TEXT) is True
    assert parser.matches("some other bank's statement") is False


def test_parse_card_payment_no_counterparty():
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-05",
                data_waluty="2026-01-05",
                typ_transakcji="Płatność",
                opis="Tytuł : SKLEP TEST 123",
                kwota="-21,70",
                saldo="+2207,85",
            ),
            *_row(112, typ_transakcji="kartą", opis="Lokalizacja : SKLEP TEST 123"),
            *_row(124, opis="Adres : UL. TESTOWA 1"),
            *_row(136, opis="Miasto : WARSZAWA"),
            *_row(148, opis="Kraj : POLSKA"),
            *_row(160, opis="Data wykonania operacji : 2026-01-04"),
            *_row(172, opis="Oryginalna kwota operacji : 21,70 PLN"),
            *_row(184, opis="Numer karty : 123456******7890"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["txn_date"] == date(2026, 1, 5)
    assert txn["amount"] == Decimal("-21.70")
    assert txn["running_balance"] == Decimal("2207.85")
    assert txn["description"] == "SKLEP TEST 123"
    assert txn["counterparty"] is None
    assert txn["raw_details"]["typ_transakcji"] == "Płatność kartą"
    assert txn["raw_details"]["lokalizacja"] == "SKLEP TEST 123"
    assert txn["raw_details"]["adres"] == "UL. TESTOWA 1"
    assert txn["raw_details"]["miasto"] == "WARSZAWA"
    assert txn["raw_details"]["kraj"] == "POLSKA"
    assert txn["raw_details"]["numer_karty"] == "123456******7890"
    assert txn["raw_details"]["oryginalna_kwota_operacji"] == "21,70 PLN"


def test_parse_amount_handles_non_breaking_space_thousands_separator():
    """Amounts over 999 use a thousands separator that isn't necessarily a
    plain ASCII space in the PDF's actual character encoding (the `kwota`/
    `saldo` values below use a real U+00A0 non-breaking space, not a plain
    " " — a real statement's amount crashed `Decimal(...)` on exactly this
    before the fix, despite looking like plain digits when printed). A
    literal ASCII space would already have worked with the old
    `.replace(" ", "")` code, so this specifically proves the fix, not just
    re-tests the already-working case.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-07",
                data_waluty="2026-01-07",
                typ_transakcji="Przelew",
                opis="Tytuł : WYPLATA TEST",
                kwota="+1 234,56",
                saldo="+5 678,90",
            ),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["amount"] == Decimal("1234.56")
    assert txn["running_balance"] == Decimal("5678.90")


def test_parse_amount_on_continuation_row_is_not_lost():
    """A real export had a transaction whose `kwota`/`saldo` landed on a
    continuation row rather than the date row itself — row-clustering
    split what's logically one entry the same way it already can for
    `typ_transakcji`/`opis` (handled), but `kwota`/`saldo` weren't merged
    from continuation rows before this fix, so the amount came back as an
    empty string and crashed `Decimal("")`.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-08",
                data_waluty="2026-01-08",
                typ_transakcji="Przelew",
                opis="Tytuł : PRZELEW TEST",
            ),
            *_row(112, kwota="-50,00", saldo="+950,00"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["amount"] == Decimal("-50.00")
    assert txn["running_balance"] == Decimal("950.00")


def test_footer_row_text_in_kwota_column_is_not_mistaken_for_amount():
    """A real export crashed with `ValueError: Could not parse amount as
    Decimal after cleanup: 'obciążeń' (...)` — the continuation-row merge
    (added to fix a previous bug) locked onto a footer/summary row's stray
    label text ("obciążeń", not a number, and safe to show since it has no
    digits) that happened to land in the kwota column's x0 range, landing
    *before* the transaction's real numeric continuation row in row order.
    Because the old code took the first non-empty value unconditionally, it
    never gave the real amount a chance. The fix must reject the
    non-numeric candidate and still pick up the real amount from the row
    after it.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-09",
                data_waluty="2026-01-09",
                typ_transakcji="Przelew",
                opis="Tytuł : PRZELEW TEST",
            ),
            *_row(106, kwota="obciążeń"),
            *_row(112, kwota="-30,00", saldo="+920,00"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["amount"] == Decimal("-30.00")
    assert txn["running_balance"] == Decimal("920.00")


def test_missing_amount_error_surfaces_other_columns_for_diagnosis():
    """When `kwota` is empty (e.g. the amount word never landed in the
    kwota x0 column at all — a live report of this had a transaction whose
    amount was nowhere to be found even after the continuation-row fixes),
    the raised error should surface the other columns' (digit-redacted)
    content too, so a column-drift theory can be confirmed/ruled out from
    the traceback alone rather than by guessing at another fix blind.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-10",
                data_waluty="2026-01-10",
                typ_transakcji="Przelew",
                opis="Tytuł : PRZELEW TEST 12345,67",
            ),
        ]
    ]

    with pytest.raises(ValueError, match="opis columns seen"):
        PkoBpHistoriaRachunkuParser().parse("", words_per_page)


def test_trailing_footer_summary_does_not_pollute_last_transaction():
    """A real export crashed with an empty-amount error whose (safe, no
    real amounts) diagnostic revealed the true cause: the statement's
    trailing footer — a "Liczba obciążeń/Suma obciążeń/Liczba uznań/Suma
    uznań" summary table, a legal disclaimer citing the Banking Law Act,
    the account number, a print-date line, and a repeated column-header
    row — was being merged into the *last real transaction* as
    continuation lines (none of it has a date, so it fell through to the
    `elif current is not None` branch). That footer content uses a
    different column layout than the transaction table, so the last
    transaction's own kwota/saldo (already present on its date row here)
    would end up silently discarded/never looked at, and the footer text
    would corrupt its description. This asserts the last transaction is
    finalized as soon as footer/header content is detected, untouched by
    it.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-11",
                data_waluty="2026-01-11",
                typ_transakcji="Przelew",
                opis="Tytuł : PRZELEW TEST",
                kwota="-40,00",
                saldo="+960,00",
            ),
            *_row(112, opis="Liczba obciążeń Suma obciążeń"),
            *_row(
                124, typ_transakcji="na podstawie", opis="art. 111 Ustawy Prawo Bankowe"
            ),
            *_row(136, opis="z późniejszymi zmianami)."),
            *_row(148, opis="data wydruku: 2026-01-15"),
            *_row(
                160, data_operacji="Data", typ_transakcji="Typ transakcji", opis="Opis"
            ),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["amount"] == Decimal("-40.00")
    assert txn["running_balance"] == Decimal("960.00")
    assert txn["description"] == "PRZELEW TEST"
    assert txn["raw_details"]["typ_transakcji"] == "Przelew"


def test_wide_amount_leaked_into_opis_column_is_reclaimed_as_kwota():
    """A real export crashed with an empty-`kwota` error whose diagnostic
    showed the `opis` column holding exactly one value shaped like an
    amount (a 4-digit thousands amount, e.g. "1 234,56") while `kwota` and
    `typ_transakcji` were both empty. Root cause: a wide, right-aligned
    amount's left edge (x0) can cross the kwota column's lower bound and
    land entirely in the `opis` bucket instead. This must be reclaimed as
    the real `kwota` rather than raising or being treated as description
    text.
    """
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-12",
                data_waluty="2026-01-12",
                opis="1 234,56",
            ),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["amount"] == Decimal("1234.56")
    assert txn["description"] == ""


def test_parse_outgoing_transfer_sets_counterparty_from_odbiorca():
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-06",
                data_waluty="2026-01-06",
                typ_transakcji="Przelew na",
                opis="Tytuł : SKLADKA TEST",
                kwota="-100,00",
                saldo="+500,00",
            ),
            *_row(112, typ_transakcji="rachunek", opis="Odbiorca : JAN KOWALSKI"),
            *_row(124, opis="Nr rachunku : 12 3456 7890"),
            *_row(136, opis="Referencje : REF123"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["counterparty"] == "JAN KOWALSKI"
    assert txn["raw_details"]["typ_transakcji"] == "Przelew na rachunek"
    assert txn["raw_details"]["nr_rachunku"] == "12 3456 7890"
    assert txn["raw_details"]["referencje"] == "REF123"


def test_parse_incoming_transfer_sets_counterparty_from_nadawca():
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-01",
                data_waluty="2026-01-01",
                typ_transakcji="Przelew z rachunku",
                opis="Tytuł : WYNAGRODZENIE",
                kwota="+5000,00",
                saldo="+8000,00",
            ),
            *_row(112, opis="Nadawca : PRACODAWCA SP. Z O.O."),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert transactions[0]["counterparty"] == "PRACODAWCA SP. Z O.O."


def test_parse_fee_has_no_counterparty():
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-02",
                data_waluty="2026-01-02",
                typ_transakcji="Prowizja",
                opis="Tytuł : PROWIZJA ZA WYPLATE",
                kwota="-9,00",
                saldo="+1765,57",
            ),
            *_row(112, opis="Referencje : TRN123"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert transactions[0]["counterparty"] is None
    assert transactions[0]["description"] == "PROWIZJA ZA WYPLATE"


def test_wrapped_title_continuation_line_has_no_colon():
    words_per_page = [
        [
            *_row(
                100,
                data_operacji="2026-01-02",
                data_waluty="2026-01-02",
                typ_transakcji="Prowizja",
                opis="Tytuł : PROWIZJA ZA WYPLATE W OBCYM",
                kwota="-9,00",
                saldo="+1765,57",
            ),
            *_row(112, opis="BANKOMACIE"),
            *_row(124, opis="Referencje : TRN123"),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert transactions[0]["description"] == "PROWIZJA ZA WYPLATE W OBCYM BANKOMACIE"
    assert transactions[0]["raw_details"]["referencje"] == "TRN123"


def test_repeated_page_header_is_not_treated_as_a_transaction():
    words_per_page = [
        [
            *_row(50, data_operacji="Data", typ_transakcji="Typ transakcji"),
            *_row(
                100,
                data_operacji="2026-01-02",
                data_waluty="2026-01-02",
                typ_transakcji="Opłata",
                opis="Tytuł : OPLATA",
                kwota="-5,00",
                saldo="+100,00",
            ),
        ]
    ]

    transactions = PkoBpHistoriaRachunkuParser().parse("", words_per_page)

    assert len(transactions) == 1
    assert transactions[0]["txn_date"] == date(2026, 1, 2)


def test_multiple_transactions_across_pages():
    page_1 = _row(
        100,
        data_operacji="2026-01-02",
        data_waluty="2026-01-02",
        typ_transakcji="Opłata",
        opis="Tytuł : A",
        kwota="-5,00",
        saldo="+100,00",
    )
    page_2 = _row(
        100,
        data_operacji="2026-01-01",
        data_waluty="2026-01-01",
        typ_transakcji="Opłata",
        opis="Tytuł : B",
        kwota="-3,00",
        saldo="+105,00",
    )

    transactions = PkoBpHistoriaRachunkuParser().parse("", [page_1, page_2])

    assert [t["description"] for t in transactions] == ["A", "B"]


# --- Generic fallback parser --------------------------------------------


def test_generic_parser_always_matches():
    assert GenericLineParser().matches("anything at all") is True


def test_generic_parser_extracts_date_description_amount():
    text = "2026-01-05 SOME SHOP PURCHASE -21,70\nnot a transaction line\n"
    transactions = GenericLineParser().parse(text, [])

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn["txn_date"] == date(2026, 1, 5)
    assert txn["description"] == "SOME SHOP PURCHASE"
    assert txn["amount"] == Decimal("-21.70")
    assert txn["counterparty"] is None
    assert txn["running_balance"] is None
    assert txn["raw_details"] == {}


# --- Full subgraph, real Postgres, fake drive client + fake extractor ---


class FakeDriveClient:
    def __init__(self, content_by_file_id: dict[str, bytes] | None = None) -> None:
        self.content_by_file_id = content_by_file_id or {}

    def download_file(self, file_id: str) -> bytes:
        return self.content_by_file_id[file_id]


async def _make_verified_statement(db_session) -> Statement:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()

    statement = Statement(
        account_id=account.id,
        drive_file_id="file-1",
        file_name="statement.pdf",
        checksum="abc123",
        status="verified",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 7),
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


async def test_persists_transactions_and_derives_statement_balances(db_session):
    statement = await _make_verified_statement(db_session)
    drive_client = FakeDriveClient({"file-1": b"irrelevant, extractor is faked"})

    # Newest-first, matching the real export's row order.
    fake_transactions = [
        RawTransaction(
            txn_date=date(2026, 1, 5),
            amount=Decimal("-21.70"),
            description="SKLEP TEST",
            counterparty=None,
            running_balance=Decimal("1767.41"),
            raw_details={"typ_transakcji": "Płatność kartą"},
        ),
        RawTransaction(
            txn_date=date(2026, 1, 1),
            amount=Decimal("6480.00"),
            description="WYNAGRODZENIE",
            counterparty="PRACODAWCA SP. Z O.O.",
            running_balance=Decimal("6991.82"),
            raw_details={"typ_transakcji": "Przelew z rachunku"},
        ),
    ]

    def fake_extractor(_content: bytes):
        return ["irrelevant text"], [[]]

    class FakeParser:
        def matches(self, _first_page_text: str) -> bool:
            return True

        def parse(self, _text, _words_per_page):
            return fake_transactions

    graph = build_extraction_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_words=fake_extractor,
        parsers=(FakeParser(),),
    )
    await graph.ainvoke({"pending": []})

    transactions = (
        (
            await db_session.execute(
                select(Transaction).where(Transaction.statement_id == statement.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(transactions) == 2
    by_description = {t.description: t for t in transactions}
    assert by_description["SKLEP TEST"].amount == Decimal("-21.70")
    assert by_description["SKLEP TEST"].counterparty is None
    assert by_description["SKLEP TEST"].raw_details == {
        "typ_transakcji": "Płatność kartą"
    }
    assert by_description["WYNAGRODZENIE"].counterparty == "PRACODAWCA SP. Z O.O."
    assert all(t.review_status == "auto" for t in transactions)

    await db_session.refresh(statement)
    assert statement.status == "verified"
    assert statement.closing_balance == Decimal("1767.41")
    # opening_balance = oldest txn's running_balance - its own amount
    assert statement.opening_balance == Decimal("6991.82") - Decimal("6480.00")


async def test_no_verified_statements_completes_without_error(db_session):
    drive_client = FakeDriveClient()

    def fake_extractor(_content: bytes):
        raise AssertionError("should never be called with zero verified statements")

    graph = build_extraction_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_words=fake_extractor,
    )
    result = await graph.ainvoke({"pending": []})

    assert result == {"pending": []}
    transactions = (await db_session.execute(select(Transaction))).scalars().all()
    assert transactions == []
