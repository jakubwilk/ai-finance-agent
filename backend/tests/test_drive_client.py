from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from finance_agent.config import Settings
from finance_agent.subgraphs.ingestion.drive_client import (
    DriveFile,
    GoogleDriveClient,
    build_credentials,
)


def _make_service_with_pages(pages: list[dict]) -> MagicMock:
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = pages
    return service


def test_list_new_files_builds_query_with_modified_after():
    service = _make_service_with_pages([{"files": []}])
    client = GoogleDriveClient(service)

    client.list_new_files("folder123", modified_after=datetime(2026, 1, 1, tzinfo=UTC))

    _, kwargs = service.files.return_value.list.call_args
    assert "'folder123' in parents" in kwargs["q"]
    assert "mimeType='application/pdf'" in kwargs["q"]
    assert "trashed=false" in kwargs["q"]
    assert "modifiedTime > '2026-01-01T00:00:00+00:00'" in kwargs["q"]


def test_list_new_files_omits_modified_after_when_not_given():
    service = _make_service_with_pages([{"files": []}])
    client = GoogleDriveClient(service)

    client.list_new_files("folder123")

    _, kwargs = service.files.return_value.list.call_args
    assert "modifiedTime" not in kwargs["q"]


def test_list_new_files_follows_pagination():
    page_one = {
        "nextPageToken": "page-2",
        "files": [
            {"id": "f1", "name": "a.pdf", "modifiedTime": "2026-01-01T00:00:00+00:00"}
        ],
    }
    page_two = {
        "files": [
            {"id": "f2", "name": "b.pdf", "modifiedTime": "2026-01-02T00:00:00+00:00"}
        ],
    }
    service = _make_service_with_pages([page_one, page_two])
    client = GoogleDriveClient(service)

    result = client.list_new_files("folder123")

    assert result == [
        DriveFile(
            id="f1", name="a.pdf", modified_time=datetime(2026, 1, 1, tzinfo=UTC)
        ),
        DriveFile(
            id="f2", name="b.pdf", modified_time=datetime(2026, 1, 2, tzinfo=UTC)
        ),
    ]
    assert service.files.return_value.list.return_value.execute.call_count == 2


def test_download_file_returns_bytes_from_chunked_download():
    service = MagicMock()
    fake_chunk = b"%PDF-1.4 fake content"

    def fake_media_io_base_download(buffer, _request):
        downloader = MagicMock()

        def next_chunk():
            buffer.write(fake_chunk)
            return (MagicMock(), True)

        downloader.next_chunk.side_effect = next_chunk
        return downloader

    with patch(
        "finance_agent.subgraphs.ingestion.drive_client.MediaIoBaseDownload",
        side_effect=fake_media_io_base_download,
    ):
        client = GoogleDriveClient(service)
        result = client.download_file("file123")

    assert result == fake_chunk
    service.files.return_value.get_media.assert_called_once_with(fileId="file123")


def test_build_credentials_raises_clear_error_when_missing():
    settings = Settings(
        google_oauth_client_id=None,
        google_oauth_client_secret=None,
        google_oauth_refresh_token=None,
    )

    with pytest.raises(RuntimeError, match="GOOGLE_OAUTH_CLIENT_ID"):
        build_credentials(settings)


def test_build_credentials_succeeds_when_all_present():
    settings = Settings(
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_refresh_token="refresh-token",
    )

    credentials = build_credentials(settings)

    assert credentials.client_id == "client-id"
    assert credentials.refresh_token == "refresh-token"
