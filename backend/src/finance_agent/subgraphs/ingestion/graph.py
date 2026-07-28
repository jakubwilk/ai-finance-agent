from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.subgraphs.ingestion.drive_client import GoogleDriveClient
from finance_agent.subgraphs.ingestion.nodes import (
    make_dedupe_check,
    make_download,
    make_list_new_files,
    make_persist_metadata,
    make_update_sync_cursor,
)
from finance_agent.subgraphs.ingestion.state import IngestionState

LIST_NEW_FILES = "list_new_files"
DEDUPE_CHECK = "dedupe_check"
DOWNLOAD = "download"
PERSIST_METADATA = "persist_metadata"
UPDATE_SYNC_CURSOR = "update_sync_cursor"


def build_ingestion_graph(
    session: AsyncSession,
    drive_client: GoogleDriveClient,
    folder_id: str | None,
) -> CompiledStateGraph:
    """Build the `ingestion` subgraph per docs/02-spec-google-drive-ingestion.md.

    `session`/`drive_client` are injected (not built internally) so callers
    control their lifecycle (a single session per subgraph run, committed by
    the caller) and tests can pass a fake drive client with zero real Drive
    calls. `folder_id` is the Drive folder ID from `.env`
    (`GOOGLE_DRIVE_FOLDER_ID` in `config.Settings`) — `None` means nothing is
    configured yet, so the subgraph runs and completes without discovering
    any files.
    """
    builder = StateGraph(IngestionState)

    builder.add_node(
        LIST_NEW_FILES,
        make_list_new_files(session, drive_client, folder_id),
    )
    builder.add_node(DEDUPE_CHECK, make_dedupe_check(session))
    builder.add_node(DOWNLOAD, make_download(drive_client))
    builder.add_node(PERSIST_METADATA, make_persist_metadata(session))
    builder.add_node(UPDATE_SYNC_CURSOR, make_update_sync_cursor(session))

    builder.add_edge(START, LIST_NEW_FILES)
    builder.add_edge(LIST_NEW_FILES, DEDUPE_CHECK)
    builder.add_edge(DEDUPE_CHECK, DOWNLOAD)
    builder.add_edge(DOWNLOAD, PERSIST_METADATA)
    builder.add_edge(PERSIST_METADATA, UPDATE_SYNC_CURSOR)
    builder.add_edge(UPDATE_SYNC_CURSOR, END)

    return builder.compile()
