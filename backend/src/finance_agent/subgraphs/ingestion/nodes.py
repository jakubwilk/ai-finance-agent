"""Node factories for the ingestion subgraph (docs/02-spec-google-drive-ingestion.md).

Each `make_*` function closes over its dependencies (`AsyncSession`,
`GoogleDriveClient`) and returns the actual async node callable — the same
dependency-injection shape as `drive_client.GoogleDriveClient` (injected
`service`) and `graph.master._make_placeholder` (factory returning a node),
so tests can inject a fake session/drive client instead of hitting real
Postgres/Drive.
"""

import hashlib
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Account, Statement
from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient
from finance_agent.subgraphs.ingestion.state import (
    DiscoveredFile,
    IngestedFile,
    IngestionState,
)

Node = Callable[[IngestionState], Awaitable[dict]]


def make_list_new_files(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    folder_id: str | None,
) -> Node:
    async def _list_new_files(_state: IngestionState) -> dict:
        if folder_id is None:
            return {"discovered": []}

        account = (await session.execute(select(Account))).scalars().first()
        if account is None:
            return {"discovered": []}

        files = drive_client.list_new_files(
            folder_id, modified_after=account.last_synced_at
        )
        discovered = [
            DiscoveredFile(
                account_id=str(account.id),
                drive_file_id=f.id,
                file_name=f.name,
                modified_time=f.modified_time,
            )
            for f in files
        ]

        return {"discovered": discovered}

    return _list_new_files


def make_dedupe_check(session: AsyncSession) -> Node:
    async def _dedupe_check(state: IngestionState) -> dict:
        discovered = state["discovered"]
        if not discovered:
            return {"to_download": []}

        account_ids = {uuid.UUID(f["account_id"]) for f in discovered}
        result = await session.execute(
            select(Statement.account_id, Statement.drive_file_id).where(
                Statement.account_id.in_(account_ids)
            )
        )
        existing = {(str(row.account_id), row.drive_file_id) for row in result}

        to_download = [
            f
            for f in discovered
            if (f["account_id"], f["drive_file_id"]) not in existing
        ]
        return {"to_download": to_download}

    return _dedupe_check


def make_download(drive_client: GoogleDriveClient) -> Node:
    async def _download(state: IngestionState) -> dict:
        ingested: list[IngestedFile] = []
        for f in state["to_download"]:
            content = drive_client.download_file(f["drive_file_id"])
            checksum = hashlib.sha256(content).hexdigest()
            ingested.append(
                IngestedFile(
                    account_id=f["account_id"],
                    drive_file_id=f["drive_file_id"],
                    file_name=f["file_name"],
                    modified_time=f["modified_time"],
                    checksum=checksum,
                )
            )
        return {"ingested": ingested}

    return _download


def make_persist_metadata(session: AsyncSession) -> Node:
    async def _persist_metadata(state: IngestionState) -> dict:
        for f in state["ingested"]:
            session.add(
                Statement(
                    account_id=uuid.UUID(f["account_id"]),
                    drive_file_id=f["drive_file_id"],
                    file_name=f["file_name"],
                    checksum=f["checksum"],
                    status="pending",
                )
            )
        await session.flush()
        return {}

    return _persist_metadata


def make_update_sync_cursor(session: AsyncSession) -> Node:
    async def _update_sync_cursor(state: IngestionState) -> dict:
        discovered = state["discovered"]
        if not discovered:
            return {}

        latest_by_account: dict[str, DiscoveredFile] = {}
        for f in discovered:
            current = latest_by_account.get(f["account_id"])
            if current is None or f["modified_time"] > current["modified_time"]:
                latest_by_account[f["account_id"]] = f

        result = await session.execute(
            select(Account).where(
                Account.id.in_(uuid.UUID(a) for a in latest_by_account)
            )
        )
        for account in result.scalars():
            account.last_synced_at = latest_by_account[str(account.id)]["modified_time"]

        return {}

    return _update_sync_cursor
