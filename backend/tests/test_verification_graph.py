from datetime import date

from finance_agent.db.models import Account, Statement
from finance_agent.subgraphs.verification.graph import build_verification_graph
from finance_agent.subgraphs.verification.nodes import (
    _extract_period,
    _is_readable,
    _parse_date,
)

EMPTY_STATE = {"results": [], "all_ok": True}

# Mirrors the exact shape pdfplumber.extract_tables() returns for the real
# PKO BP "Zastosowane kryteria wyboru" table (verified against the user's
# sample statement) — values here are made up, not the user's real dates.
CRITERIA_TABLE = [
    ["Zastosowane kryteria wyboru", None, None, None],
    ["Od dnia", "2026-01-01", "Kwota min", "-"],
    ["Do dnia", "2026-01-07", "Kwota max", "-"],
    ["Typ operacji", "Wszystkie", None, None],
]


class FakeDriveClient:
    def __init__(self, content_by_file_id: dict[str, bytes] | None = None) -> None:
        self.content_by_file_id = content_by_file_id or {}

    def download_file(self, file_id: str) -> bytes:
        return self.content_by_file_id[file_id]


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_pending_statement(
    db_session, account: Account, drive_file_id: str = "file-1"
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="pending",
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


# --- Pure parsing logic (no PDF bytes, no DB) ---------------------------


def test_is_readable_true_for_nonempty_text():
    assert _is_readable("HISTORIA RACHUNKU\nOd dnia 2026-01-01") is True


def test_is_readable_false_for_blank_text():
    assert _is_readable("   \n  ") is False
    assert _is_readable("") is False


def test_extract_period_finds_od_dnia_and_do_dnia():
    period_start, period_end = _extract_period([CRITERIA_TABLE])
    assert period_start == date(2026, 1, 1)
    assert period_end == date(2026, 1, 7)


def test_extract_period_returns_none_when_labels_missing():
    other_table = [["Typ operacji", "Wszystkie", None, None]]
    period_start, period_end = _extract_period([other_table])
    assert period_start is None
    assert period_end is None


def test_parse_date_returns_none_for_invalid_format():
    assert _parse_date("29 stycznia 2026") is None
    assert _parse_date("2026-01-01") == date(2026, 1, 1)


# --- Full subgraph, real Postgres, fake drive client + fake extractor ---


async def test_readable_statement_with_parseable_period_is_verified(db_session):
    account = await _make_account(db_session)
    statement = await _make_pending_statement(db_session, account)
    drive_client = FakeDriveClient({"file-1": b"irrelevant, extractor is faked"})

    def fake_extractor(_content: bytes):
        return "HISTORIA RACHUNKU", [CRITERIA_TABLE]

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=fake_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is True
    await db_session.refresh(statement)
    assert statement.status == "verified"
    assert statement.period_start == date(2026, 1, 1)
    assert statement.period_end == date(2026, 1, 7)
    assert statement.failure_reason is None


async def test_unreadable_statement_is_marked_failed(db_session):
    account = await _make_account(db_session)
    statement = await _make_pending_statement(db_session, account)
    drive_client = FakeDriveClient({"file-1": b"scanned image, no text layer"})

    def fake_extractor(_content: bytes):
        return "", []

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=fake_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "unreadable_pdf"


async def test_extractor_exception_is_treated_as_unreadable(db_session):
    account = await _make_account(db_session)
    statement = await _make_pending_statement(db_session, account)
    drive_client = FakeDriveClient({"file-1": b"corrupted"})

    def failing_extractor(_content: bytes):
        raise ValueError("not a valid PDF")

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=failing_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "unreadable_pdf"


async def test_unparseable_period_is_marked_failed(db_session):
    account = await _make_account(db_session)
    statement = await _make_pending_statement(db_session, account)
    drive_client = FakeDriveClient({"file-1": b"irrelevant, extractor is faked"})

    def fake_extractor(_content: bytes):
        return "HISTORIA RACHUNKU", [[["Typ operacji", "Wszystkie", None, None]]]

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=fake_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "unparseable_period"


async def test_overlapping_period_is_marked_duplicate(db_session):
    account = await _make_account(db_session)
    db_session.add(
        Statement(
            account_id=account.id,
            drive_file_id="existing-file",
            file_name="old.pdf",
            checksum="deadbeef",
            status="verified",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 7),
        )
    )
    statement = await _make_pending_statement(
        db_session, account, drive_file_id="file-2"
    )
    drive_client = FakeDriveClient({"file-2": b"irrelevant, extractor is faked"})

    # Overlaps the existing verified statement's period (2026-01-01 .. 01-07).
    overlapping_table = [
        ["Od dnia", "2026-01-05", "Kwota min", "-"],
        ["Do dnia", "2026-01-10", "Kwota max", "-"],
    ]

    def fake_extractor(_content: bytes):
        return "HISTORIA RACHUNKU", [overlapping_table]

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=fake_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["all_ok"] is False
    await db_session.refresh(statement)
    assert statement.status == "failed"
    assert statement.failure_reason == "duplicate_statement"


async def test_zero_pending_statements_completes_with_all_ok_true(db_session):
    drive_client = FakeDriveClient()

    def fake_extractor(_content: bytes):
        raise AssertionError("should never be called with zero pending statements")

    graph = build_verification_graph(
        session=db_session,
        drive_client=drive_client,
        extract_text_and_tables=fake_extractor,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result == {"results": [], "all_ok": True}
