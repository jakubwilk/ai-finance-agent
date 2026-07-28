from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from finance_agent.db.models import Account, Statement
from finance_agent.subgraphs.ingestion.drive_client import DriveFile
from finance_agent.subgraphs.ingestion.graph import build_ingestion_graph
from finance_agent.subgraphs.ingestion.nodes import make_dedupe_check

EMPTY_STATE = {"discovered": [], "to_download": [], "ingested": []}
FOLDER_ID = "folder-1"


class FakeDriveClient:
    """Duck-typed stand-in for GoogleDriveClient — no googleapiclient involved.

    `files_by_folder`/`content_by_file_id` are configured per test; real
    calls are recorded so tests can assert `modified_after` was forwarded.
    """

    def __init__(
        self,
        files_by_folder: dict[str, list[DriveFile]] | None = None,
        content_by_file_id: dict[str, bytes] | None = None,
    ) -> None:
        self.files_by_folder = files_by_folder or {}
        self.content_by_file_id = content_by_file_id or {}
        self.list_calls: list[tuple[str, datetime | None]] = []

    def list_new_files(
        self, folder_id: str, modified_after: datetime | None = None
    ) -> list[DriveFile]:
        self.list_calls.append((folder_id, modified_after))
        return self.files_by_folder.get(folder_id, [])

    def download_file(self, file_id: str) -> bytes:
        return self.content_by_file_id[file_id]


async def _make_account(db_session):
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def test_dedupe_check_skips_already_known_drive_file_id(db_session):
    account = await _make_account(db_session)
    db_session.add(
        Statement(
            account_id=account.id,
            drive_file_id="existing-file",
            file_name="old.pdf",
            checksum="deadbeef",
            status="pending",
        )
    )
    await db_session.flush()

    node = make_dedupe_check(db_session)
    result = await node(
        {
            **EMPTY_STATE,
            "discovered": [
                {
                    "account_id": str(account.id),
                    "drive_file_id": "existing-file",
                    "file_name": "old.pdf",
                    "modified_time": datetime(2026, 1, 1, tzinfo=UTC),
                },
                {
                    "account_id": str(account.id),
                    "drive_file_id": "new-file",
                    "file_name": "new.pdf",
                    "modified_time": datetime(2026, 1, 2, tzinfo=UTC),
                },
            ],
        }
    )

    assert [f["drive_file_id"] for f in result["to_download"]] == ["new-file"]


async def test_full_subgraph_persists_new_statement_and_advances_cursor(db_session):
    account = await _make_account(db_session)
    modified_time = datetime(2026, 1, 15, tzinfo=UTC)
    drive_client = FakeDriveClient(
        files_by_folder={
            "folder-1": [
                DriveFile(
                    id="file-1", name="statement.pdf", modified_time=modified_time
                )
            ]
        },
        content_by_file_id={"file-1": b"%PDF-1.4 fake content"},
    )

    graph = build_ingestion_graph(
        session=db_session,
        drive_client=drive_client,
        folder_id=FOLDER_ID,
    )
    await graph.ainvoke(EMPTY_STATE)
    await db_session.flush()

    statements = (
        (
            await db_session.execute(
                select(Statement).where(Statement.account_id == account.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(statements) == 1
    statement = statements[0]
    assert statement.drive_file_id == "file-1"
    assert statement.status == "pending"
    assert statement.period_start is None
    assert statement.opening_balance is None
    import hashlib

    assert statement.checksum == hashlib.sha256(b"%PDF-1.4 fake content").hexdigest()

    await db_session.refresh(account)
    assert account.last_synced_at == modified_time


async def test_zero_new_files_completes_without_error_or_new_rows(db_session):
    await _make_account(db_session)
    drive_client = FakeDriveClient(files_by_folder={})

    graph = build_ingestion_graph(
        session=db_session,
        drive_client=drive_client,
        folder_id=FOLDER_ID,
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["discovered"] == []
    statements = (await db_session.execute(select(Statement))).scalars().all()
    assert statements == []


async def test_running_twice_with_same_file_inserts_only_once(db_session):
    account = await _make_account(db_session)
    modified_time = datetime(2026, 2, 1, tzinfo=UTC)
    drive_client = FakeDriveClient(
        files_by_folder={
            "folder-1": [
                DriveFile(
                    id="file-1", name="statement.pdf", modified_time=modified_time
                )
            ]
        },
        content_by_file_id={"file-1": b"content"},
    )

    graph = build_ingestion_graph(
        session=db_session,
        drive_client=drive_client,
        folder_id=FOLDER_ID,
    )
    await graph.ainvoke(EMPTY_STATE)
    await db_session.flush()

    # Second run: same discovered file (as if list_new_files hadn't advanced
    # far enough) should be skipped by dedupe_check, not violate the unique
    # constraint.
    await graph.ainvoke(EMPTY_STATE)
    await db_session.flush()

    statements = (
        (
            await db_session.execute(
                select(Statement).where(Statement.account_id == account.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(statements) == 1


async def test_no_configured_folder_id_skips_entirely(db_session):
    """When GOOGLE_DRIVE_FOLDER_ID is unset (folder_id=None), the subgraph
    completes without making any Drive call."""
    await _make_account(db_session)
    drive_client = FakeDriveClient()

    graph = build_ingestion_graph(
        session=db_session,
        drive_client=drive_client,
        folder_id=None,
    )
    await graph.ainvoke(EMPTY_STATE)

    assert drive_client.list_calls == []


async def test_drive_client_error_is_not_swallowed(db_session):
    await _make_account(db_session)

    class FailingDriveClient(FakeDriveClient):
        def list_new_files(self, folder_id, modified_after=None):
            raise RuntimeError("Drive auth token expired")

    graph = build_ingestion_graph(
        session=db_session,
        drive_client=FailingDriveClient(),
        folder_id=FOLDER_ID,
    )

    with pytest.raises(RuntimeError, match="Drive auth token expired"):
        await graph.ainvoke(EMPTY_STATE)
