import operator
from datetime import datetime
from typing import Annotated

from typing_extensions import TypedDict


class DiscoveredFile(TypedDict):
    """A file found on Drive by `list_new_files`, not yet downloaded."""

    account_id: str
    drive_file_id: str
    file_name: str
    modified_time: datetime


class IngestedFile(TypedDict):
    """A file that survived dedupe and was downloaded — checksum only, never
    the raw bytes (fetch-on-demand: nothing but this metadata is kept once
    the node returns, see docs/02-spec-google-drive-ingestion.md).
    """

    account_id: str
    drive_file_id: str
    file_name: str
    modified_time: datetime
    checksum: str


class IngestionState(TypedDict):
    """State for the ingestion subgraph (docs/02-spec-google-drive-ingestion.md).

    Deliberately never carries raw PDF bytes — only enough metadata to
    dedupe, persist `STATEMENTS` rows, and advance each account's sync
    cursor.
    """

    discovered: Annotated[list[DiscoveredFile], operator.add]
    to_download: list[DiscoveredFile]
    ingested: Annotated[list[IngestedFile], operator.add]
